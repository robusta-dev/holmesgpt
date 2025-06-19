# Troubleshooting Node Not Ready

## Before Start

You are debugging nodes in an Azure Kubernetes Service cluster. You should use aks/node-health and aks/core toolsets as much as you can to get information.
When checking node not ready issues, a detailed root cause is needed. For example, if the kubelet is stopped, you need to analyse why it's stopped.
Do not give "likely" root cause, the root cause should be deterministc. If the information in node events is not enough to give a deterministic answer, try to use more tools to get more information.
For kubelet down issues, always try to fetch kubelet logs before giving the final root cause.
For any commands running on the node level, you should always use vmss_run_command tool to run commands on the node, instead of running commands directly on the node.

## Symptoms

* Node status shows `NotReady` when running `kubectl get nodes`
* Pods scheduled on the node may be stuck in `Pending` state or evicted
* New pods are not scheduled on the affected node
* `kubectl describe node <node-name>` shows error conditions

## Possible Causes

1. **Kubelet Issues**: Kubelet service not running or encountering errors
2. **Network Problems**: Node cannot communicate with the control plane/API server
3. **Resource Exhaustion**: Node is experiencing memory, CPU, or disk pressure
4. **Certificate Issues**: Expired or invalid kubelet certificates
5. **Container Runtime Issues**: Docker, containerd, or CRI-O runtime problems
6. **Cloud Provider Issues**: Issues with underlying cloud infrastructure
7. **Node Cordoned**: Node was manually cordoned for maintenance
8. **CNI Problems**: Container Network Interface plugin issues

### 1. Check Node Status and Conditions

tools may use:
- check_node_status
- describe_node
- get_node_events

Look for specific conditions like `Ready`, `MemoryPressure`, `DiskPressure`, `NetworkUnavailable`, etc.

### 2. Check Kubelet Status

If you believe the issue is directly or indirectly caused by kubelet down or misfunctioning, 
check the kubelet status and logs.

tools may use:
- vmss_run_command, suggested SHELL_COMMAND: 
  - systemctl status kubelet
  - journalctl -u kubelet -n 100 --no-pager

### 3. Check System Resources

If you believe the issue is directly or indirectly caused by resource exhaustion, check the system resources.

tools may use:
- vmss_run_command, suggested SHELL_COMMAND: 
  - df -h
  - free -m
  - top
  - dmesg | tail -n 100

### 4. Check Container Runtime

If you believe the issue is directly or indirectly caused by container runtime issues, 
check the container runtime status and logs.

tools may use:
- vmss_run_command, suggested SHELL_COMMAND: 
  - systemctl status containerd 
  - journalctl -u containerd -n 100 --no-pager


### 5. Check Network Connectivity

If you believe the issue is directly or indirectly caused by outbound network connectivity issues,
check the network connectivity to the API server and CNI plugins.

tools may use:
- get_api_server_public_ip
- vmss_run_command, suggested SHELL_COMMAND:
  - to check connectivity to the API server, nc -zv {{ API_SERVER_PUBLIC_IP }} 443 
  - to check CNI plugins, ls -la /etc/cni/net.d/, cat /etc/cni/net.d/{{ NETWORK_CONFIG_FILE }}

