#!/usr/bin/env python3

import subprocess
import time
import sys
import argparse
from kubernetes import client, config
from kubernetes.client.rest import ApiException

NAMESPACE = "rabbitmq"
TARGET_POD_NAME = "rabbitmq-0"
POD_LABEL_SELECTOR = "app.kubernetes.io/name=rabbitmq"
CHECK_INTERVAL_SECONDS = 5
COMMAND_RUNNER = "docker"

try:
    try:
        config.load_kube_config()
    except config.ConfigException:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            raise Exception("Could not configure Kubernetes client.")

    v1 = client.CoreV1Api()
    print("Kubernetes client initialized successfully.")
except Exception as e:
    print(f"Error initializing Kubernetes client: {e}", file=sys.stderr)
    sys.exit(1)


def get_rabbitmq_pods_info(api_instance, namespace, label_selector):
    pods_info = []
    print(f"Listing pods in namespace '{namespace}' with label selector '{label_selector}'...")
    try:
        pods = api_instance.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector
        )
        if not pods.items:
             print(f"Warning: No pods found matching label selector '{label_selector}' in namespace '{namespace}'.")

        for pod in pods.items:
            if not pod.metadata.name.startswith("rabbitmq-"):
                continue

            pod_ip = pod.status.pod_ip
            node_name = pod.spec.node_name
            phase = pod.status.phase

            pods_info.append({
                "name": pod.metadata.name,
                "ip": pod_ip,
                "node": node_name,
                "status": phase
            })
            print(f"  - Found Pod: {pod.metadata.name}, Status: {phase}, IP: {pod_ip}, Node: {node_name}")

        return pods_info
    except ApiException as e:
        print(f"Error listing pods: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred while getting pod info: {e}", file=sys.stderr)
        return None


def wait_for_pods_running(api_instance, namespace, label_selector, target_count=None):
    print("\n--- Waiting for all RabbitMQ pods to be Running ---")
    while True:
        all_running = True
        pods_data = get_rabbitmq_pods_info(api_instance, namespace, label_selector)

        if pods_data is None:
            print(f"Error retrieving pod data. Retrying in {CHECK_INTERVAL_SECONDS} seconds...")
            time.sleep(CHECK_INTERVAL_SECONDS)
            continue

        if not pods_data:
            print(f"No pods found yet. Waiting...")
            all_running = False

        if target_count is not None and len(pods_data) != target_count:
             print(f"Waiting for {target_count} pods, found {len(pods_data)}. Retrying...")
             all_running = False

        current_statuses = []
        for pod in pods_data:
            status = pod.get('status', 'Unknown')
            ip = pod.get('ip', 'N/A')
            node = pod.get('node', 'N/A')
            current_statuses.append(f"{pod['name']}({status}, IP:{ip}, Node:{node})")

            if status != "Running" or not ip or not node:
                all_running = False

        print(f"Current Pod Statuses: {', '.join(current_statuses) or 'None found'}")

        if all_running and pods_data:
            print("All required RabbitMQ pods are running and have IPs/Nodes.")
            return pods_data
        else:
            print(f"Not all pods are ready. Waiting {CHECK_INTERVAL_SECONDS} seconds...")
            time.sleep(CHECK_INTERVAL_SECONDS)


def run_command_on_node(node_name, command, action):
    exec_command = [COMMAND_RUNNER, "exec", node_name, "bash", "-c", command]
    print(f"  Executing on node '{node_name}': {' '.join(exec_command)}")
    try:
        result = subprocess.run(exec_command, capture_output=True, text=True, check=False, timeout=30)

        if result.stdout:
            print(f"    stdout: {result.stdout.strip()}")
        if result.stderr:
             stderr_lower = result.stderr.strip().lower()
             # For remove, non-existence is not a failure. Print as info.
             if action == "remove" and ("no chain/target/match by that name" in stderr_lower or "rule not found" in stderr_lower):
                 print(f"    Info: {result.stderr.strip()}")
             # Otherwise print as stderr only if command failed
             elif result.returncode != 0:
                 print(f"    stderr: {result.stderr.strip()}", file=sys.stderr)
             else: # Print as regular output if command succeeded but had stderr (e.g., warnings)
                 print(f"    stderr: {result.stderr.strip()}")


        if result.returncode != 0:
             stderr_lower = result.stderr.strip().lower()
             if action == "remove" and ("no chain/target/match by that name" in stderr_lower or "rule not found" in stderr_lower):
                  print(f"    Note: Rule likely did not exist or was already removed.")
                  return True
             else:
                  print(f"    Command failed with exit code {result.returncode}", file=sys.stderr)
                  return False

        if action == "add" and "already exists" in result.stderr.lower():
             print("    Note: iptables rule likely already exists.")

        return True

    except subprocess.TimeoutExpired:
        print(f"  Error: Command timed out on node {node_name}", file=sys.stderr)
        return False
    except FileNotFoundError:
         print(f"  Error: '{COMMAND_RUNNER}' command not found. Is it installed and in the PATH?", file=sys.stderr)
         sys.exit(1)
    except Exception as e:
        print(f"  Error executing command on node {node_name}: {e}", file=sys.stderr)
        return False


def manage_iptables_rules(api_instance, namespace, label_selector, target_pod_name, command_runner, action):
    pod_data = wait_for_pods_running(api_instance, namespace, label_selector)

    if not pod_data:
        print("Failed to get running pod data. Exiting.", file=sys.stderr)
        sys.exit(1)

    target_pod_ip = None
    other_pod_ips = []
    all_nodes = set()

    print("\n--- Processing Pod Information ---")
    for pod in pod_data:
        node = pod.get('node')
        ip = pod.get('ip')
        name = pod.get('name')

        if not node or not ip or not name:
             print(f"Warning: Skipping pod {name} due to missing node/ip information.", file=sys.stderr)
             continue

        print(f"Processing Pod: {name} (IP: {ip}, Node: {node})")
        all_nodes.add(node)

        if name == target_pod_name:
            target_pod_ip = ip
            print(f"  -> Identified Target Pod '{target_pod_name}' with IP: {target_pod_ip}")
        elif name.startswith("rabbitmq-"):
            other_pod_ips.append(ip)
            print(f"  -> Identified Other RabbitMQ Pod '{name}' with IP: {ip}")

    if not target_pod_ip:
        print(f"Error: Target pod '{target_pod_name}' not found or has no IP among running pods.", file=sys.stderr)
        sys.exit(1)

    if not other_pod_ips:
        print(f"Warning: No other RabbitMQ pods found to isolate from/to. No iptables rules will be {action}ed.", file=sys.stdout)

    if not all_nodes:
        print("Error: No nodes found hosting the RabbitMQ pods.", file=sys.stderr)
        sys.exit(1)

    print(f"\nTarget Pod IP ('{target_pod_name}'): {target_pod_ip}")
    print(f"Other RabbitMQ Pod IPs: {other_pod_ips or 'None'}")
    print(f"Worker nodes involved: {list(all_nodes)}")

    iptables_flag = "-I" if action == "add" else "-D"
    action_verb = "Adding" if action == "add" else "Removing"
    action_past = "applied" if action == "add" else "removed"

    print(f"\n--- {action_verb} iptables rules ---")
    if not other_pod_ips:
        print(f"Skipping rule {action} as no 'other' pods were found.")
    else:
        overall_success = True
        for node in all_nodes:
            print(f"\nProcessing node: {node}")
            node_success = True
            for other_ip in other_pod_ips:
                if other_ip == target_pod_ip:
                     continue

                cmd1 = f"iptables {iptables_flag} FORWARD -s {target_pod_ip} -d {other_ip} -p tcp -j DROP"
                if not run_command_on_node(node, cmd1, action):
                    node_success = False

                cmd2 = f"iptables {iptables_flag} FORWARD -s {other_ip} -d {target_pod_ip} -p tcp -j DROP"
                if not run_command_on_node(node, cmd2, action):
                    node_success = False

            if not node_success:
                 overall_success = False
                 print(f"Warning: Failed to {action} some rules on node '{node}'. Check logs above.", file=sys.stderr)


        if overall_success:
             print(f"\n--- iptables rules {action_past} successfully on all relevant nodes ---")
        else:
             print(f"\n--- Warning: Some iptables rules failed to be {action_past}. Check logs above. ---", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add or remove iptables rules to isolate the rabbitmq-0 pod.")
    parser.add_argument(
        'action',
        choices=['add', 'remove'],
        help="Specify 'add' to insert iptables rules or 'remove' to delete them."
    )
    args = parser.parse_args()

    manage_iptables_rules(v1, NAMESPACE, POD_LABEL_SELECTOR, TARGET_POD_NAME, COMMAND_RUNNER, action=args.action)

    print("\nScript finished.")
