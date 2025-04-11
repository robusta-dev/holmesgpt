import kubernetes
import os
from kubernetes.client.rest import ApiException

def find_rabbitmq_services():
    """
    Autodiscovers RabbitMQ services within a Kubernetes cluster across all namespaces.

    Tries to load configuration from incluster_config first (if running inside a pod),
    then falls back to kube_config (for running locally).

    Identifies RabbitMQ services based on common labels or port names/numbers.

    Returns:
        list: A list of dictionaries, where each dictionary contains information
              about a discovered RabbitMQ service (name, namespace, cluster_ip, ports).
              Returns an empty list if no services are found or an error occurs.
              Prints error messages to stderr in case of exceptions.
    """
    discovered_services = []

    try:
        # Try loading incluster config first
        try:
            print("Attempting to load in-cluster K8s config...")
            kubernetes.config.load_incluster_config()
            print("Successfully loaded in-cluster K8s config.")
        except kubernetes.config.ConfigException:
            print("Failed to load in-cluster config. Falling back to kube config...")
            try:
                kubernetes.config.load_kube_config()
                print("Successfully loaded K8s config from kube_config.")
            except Exception as e:
                print(f"Error loading K8s configuration: {e}")
                return [] # Cannot proceed without config

        # Create an API client
        v1 = kubernetes.client.CoreV1Api()

        print("Listing services in all namespaces...")
        # List services across all namespaces
        ret = v1.list_service_for_all_namespaces(watch=False)
        print(f"Found {len(ret.items)} services in total.")

        for svc in ret.items:
            metadata = svc.metadata
            spec = svc.spec
            ports = spec.ports
            labels = metadata.labels or {} # Ensure labels is a dict even if None

            is_rabbitmq = False

            # --- Identification Criteria ---

            # 1. Check common labels
            common_labels = {
                'app': 'rabbitmq',
                'app.kubernetes.io/name': 'rabbitmq',
                'app.kubernetes.io/component': 'rabbitmq',
                'component': 'rabbitmq',
                'service': 'rabbitmq',
                'name': 'rabbitmq',
                'release': 'rabbitmq', # Often used by Helm charts
            }
            for key, value in common_labels.items():
                if labels.get(key) == value:
                    is_rabbitmq = True
                    print(f"Found potential RabbitMQ service '{metadata.name}' in namespace '{metadata.namespace}' via label '{key}={value}'")
                    break

            # 2. Check service name (less reliable, but common)
            if not is_rabbitmq and 'rabbitmq' in metadata.name.lower():
                 is_rabbitmq = True
                 print(f"Found potential RabbitMQ service '{metadata.name}' in namespace '{metadata.namespace}' via service name")


            # 3. Check for standard RabbitMQ ports (AMQP 5672, Management 15672)
            #    This is a strong indicator, especially if combined with labels/name
            if ports:
                for port in ports:
                    # Check standard AMQP port number or name
                    if port.port == 5672 or port.name == 'amqp':
                         if not is_rabbitmq: # Only print if not already identified
                              print(f"Found potential RabbitMQ service '{metadata.name}' in namespace '{metadata.namespace}' via port 5672/amqp")
                         is_rabbitmq = True
                         break # Found a key port, no need to check others for *identification*
                    # Optionally check management port
                    # if port.port == 15672 or port.name in ['http', 'management', 'prometheus']:
                    #    is_rabbitmq = True
                    #    print(f"Found potential RabbitMQ service '{metadata.name}' in namespace '{metadata.namespace}' via port 15672/management")
                    #    break

            # --- Collect Information ---
            if is_rabbitmq:
                service_info = {
                    "name": metadata.name,
                    "namespace": metadata.namespace,
                    "cluster_ip": spec.cluster_ip if spec.cluster_ip else "N/A (Headless or ExternalName)",
                    "ports": [],
                    "labels": labels
                }
                if ports:
                    for p in ports:
                        service_info["ports"].append({
                            "name": p.name if p.name else "N/A",
                            "port": p.port,
                            "protocol": p.protocol,
                            "targetPort": p.target_port if p.target_port else "N/A"
                        })
                discovered_services.append(service_info)

    except ApiException as e:
        print(f"Error calling Kubernetes API: {e.status} - {e.reason}")
        print(f"Body: {e.body}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print(f"Finished discovery. Found {len(discovered_services)} potential RabbitMQ services.")
    return discovered_services
