"""Service discovery for AlertManager instances."""

import logging
import os
import re
from typing import List, Optional

from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException
from holmes.alert_proxy.kube_proxy import KubeProxy
from holmes.alert_proxy.models import AlertManagerInstance

logger = logging.getLogger(__name__)


class AlertManagerDiscovery:
    """Discovers AlertManager instances in Kubernetes cluster."""

    # Common AlertManager service name patterns
    ALERTMANAGER_PATTERNS = [
        r".*alertmanager.*",
        r".*prometheus-alertmanager.*",
        r".*kube-prometheus.*alertmanager.*",
        r".*victoria-metrics.*alertmanager.*",
    ]

    # Common AlertManager ports
    ALERTMANAGER_PORTS = [9093, 9094]

    def __init__(self, kubeconfig_path: Optional[str] = None, use_proxy: bool = True):
        """Initialize discovery with Kubernetes client."""
        self.use_proxy = use_proxy
        self.kube_proxy = KubeProxy(kubeconfig_path) if use_proxy else None

        try:
            if kubeconfig_path:
                k8s_config.load_kube_config(config_file=kubeconfig_path)
            else:
                # Try in-cluster config first, then default kubeconfig
                try:
                    k8s_config.load_incluster_config()
                    logger.info("Using in-cluster Kubernetes config")
                    self.use_proxy = False  # Don't need proxy in-cluster
                except Exception:
                    k8s_config.load_kube_config()
                    logger.info("Using kubeconfig")

            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.k8s_available = True
        except Exception as e:
            logger.warning(f"Kubernetes API not available: {e}")
            self.k8s_available = False

    def discover_all(self) -> List[AlertManagerInstance]:
        """Discover all AlertManager instances using multiple methods."""
        discovered = []

        if self.k8s_available:
            # Method 1: Service discovery
            discovered.extend(self.discover_via_services())

            # Method 2: StatefulSet/Deployment discovery
            discovered.extend(self.discover_via_workloads())

            # Method 3: Pod label discovery
            discovered.extend(self.discover_via_pod_labels())

        # Method 4: Environment variables or config
        discovered.extend(self.discover_via_env())

        # Deduplicate by service name and namespace
        seen_keys = set()
        unique = []
        for am in discovered:
            key = f"{am.namespace}/{am.name}"
            if key not in seen_keys:
                unique.append(am)
                seen_keys.add(key)

        logger.info(f"Discovered {len(unique)} AlertManager instance(s)")
        return unique

    def discover_via_services(self) -> List[AlertManagerInstance]:
        """Discover AlertManager via Kubernetes services."""
        discovered = []

        try:
            services = self.v1.list_service_for_all_namespaces()

            for svc in services.items:
                # Check if service name matches AlertManager patterns
                for pattern in self.ALERTMANAGER_PATTERNS:
                    if re.match(pattern, svc.metadata.name, re.IGNORECASE):
                        # Check if service has ready endpoints (backing pods)
                        try:
                            endpoints = self.v1.read_namespaced_endpoints(
                                svc.metadata.name, svc.metadata.namespace
                            )
                            has_endpoints = False
                            if endpoints.subsets:
                                for subset in endpoints.subsets:
                                    if subset.addresses and len(subset.addresses) > 0:
                                        has_endpoints = True
                                        break
                        except Exception:
                            has_endpoints = (
                                True  # Assume it has endpoints if we can't check
                            )

                        if not has_endpoints:
                            logger.debug(
                                f"Skipping {svc.metadata.name} - no endpoints available"
                            )
                            break

                        # Find the right port
                        port = self._find_alertmanager_port(svc)
                        if port:
                            # Build AlertManager instance
                            use_proxy = bool(
                                self.use_proxy
                                and self.kube_proxy
                                and self.kube_proxy.available
                            )

                            # If we can use proxy, set the URL to the proxy URL
                            if use_proxy and self.kube_proxy:
                                url = self.kube_proxy.get_service_proxy_url(
                                    svc.metadata.name, svc.metadata.namespace, port
                                )
                            else:
                                # Direct cluster URL
                                url = f"http://{svc.metadata.name}.{svc.metadata.namespace}.svc.cluster.local:{port}"

                            discovered.append(
                                AlertManagerInstance(
                                    name=svc.metadata.name,
                                    namespace=svc.metadata.namespace,
                                    url=url,
                                    port=port,
                                    source="service",
                                    use_proxy=use_proxy,
                                )
                            )
                            logger.info(
                                f"Found AlertManager service: {svc.metadata.name} in {svc.metadata.namespace}:{port}"
                            )
                        break
        except ApiException as e:
            logger.error(f"Failed to list services: {e}")

        return discovered

    def discover_via_workloads(self) -> List[AlertManagerInstance]:
        """Discover AlertManager via StatefulSets and Deployments."""
        discovered = []

        try:
            # Check StatefulSets
            statefulsets = self.apps_v1.list_stateful_set_for_all_namespaces()
            for sts in statefulsets.items:
                if self._is_alertmanager_workload(sts.metadata.name):
                    # Try to construct service URL
                    url = self._construct_url_from_workload(sts, "statefulset")
                    if url:
                        discovered.append(
                            AlertManagerInstance(
                                name=sts.metadata.name,
                                namespace=sts.metadata.namespace,
                                url=url,
                                source="statefulset",
                            )
                        )

            # Check Deployments
            deployments = self.apps_v1.list_deployment_for_all_namespaces()
            for dep in deployments.items:
                if self._is_alertmanager_workload(dep.metadata.name):
                    url = self._construct_url_from_workload(dep, "deployment")
                    if url:
                        discovered.append(
                            AlertManagerInstance(
                                name=dep.metadata.name,
                                namespace=dep.metadata.namespace,
                                url=url,
                                source="deployment",
                            )
                        )
        except ApiException as e:
            logger.error(f"Failed to list workloads: {e}")

        return discovered

    def discover_via_pod_labels(self) -> List[AlertManagerInstance]:
        """Discover AlertManager via pod labels."""
        discovered = []

        label_selectors = [
            "app=alertmanager",
            "app.kubernetes.io/name=alertmanager",
            "component=alertmanager",
        ]

        try:
            for selector in label_selectors:
                pods = self.v1.list_pod_for_all_namespaces(label_selector=selector)
                for pod in pods.items:
                    if pod.status.phase == "Running":
                        # Get the first container port that looks like AlertManager
                        for container in pod.spec.containers:
                            for port in container.ports or []:
                                if port.container_port in self.ALERTMANAGER_PORTS:
                                    url = f"http://{pod.status.pod_ip}:{port.container_port}"
                                    discovered.append(
                                        AlertManagerInstance(
                                            name=pod.metadata.name,
                                            namespace=pod.metadata.namespace,
                                            url=url,
                                            source="pod",
                                        )
                                    )
                                    break
        except ApiException as e:
            logger.error(f"Failed to list pods: {e}")

        return discovered

    def discover_via_env(self) -> List[AlertManagerInstance]:
        """Discover AlertManager via environment variables."""

        discovered = []

        # Check common environment variables
        alertmanager_url = os.getenv("ALERTMANAGER_URL")
        if alertmanager_url:
            discovered.append(
                AlertManagerInstance(
                    name="env-configured",
                    namespace="unknown",
                    url=alertmanager_url,
                    source="environment",
                )
            )

        return discovered

    def _find_alertmanager_port(self, service) -> Optional[int]:
        """Find the AlertManager port from a service."""
        for port in service.spec.ports:
            # Check by port number
            if port.port in self.ALERTMANAGER_PORTS:
                return port.port
            # Check by port name
            if port.name and "alertmanager" in port.name.lower():
                return port.port
            # Check by target port
            if port.target_port and str(port.target_port) in map(
                str, self.ALERTMANAGER_PORTS
            ):
                return port.port

        # Default to 9093 if service matches but no specific port found
        return 9093

    def _is_alertmanager_workload(self, name: str) -> bool:
        """Check if a workload name matches AlertManager patterns."""
        for pattern in self.ALERTMANAGER_PATTERNS:
            if re.match(pattern, name, re.IGNORECASE):
                return True
        return False

    def _construct_url_from_workload(
        self, workload, workload_type: str
    ) -> Optional[str]:
        """Construct AlertManager URL from workload."""
        # For StatefulSets, assume headless service exists
        if workload_type == "statefulset":
            # Common pattern: alertmanager-name -> alertmanager-name (headless service)
            service_name = workload.metadata.name
            if "-alertmanager" in service_name:
                service_name = service_name.replace("-alertmanager", "")
            return f"http://{service_name}.{workload.metadata.namespace}.svc.cluster.local:9093"

        # For Deployments, harder to guess service name
        return None
