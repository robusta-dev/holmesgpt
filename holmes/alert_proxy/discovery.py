"""Service discovery for AlertManager instances."""

import logging
import re
from typing import Dict, List, Optional

import requests
from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException
from holmes.alert_proxy.kube_proxy import KubeProxy

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

    async def discover_all(self) -> List[Dict[str, str]]:
        """Discover all AlertManager instances using multiple methods."""
        discovered = []

        if self.k8s_available:
            # Method 1: Service discovery
            discovered.extend(await self.discover_via_services())

            # Method 2: StatefulSet/Deployment discovery
            discovered.extend(await self.discover_via_workloads())

            # Method 3: Pod label discovery
            discovered.extend(await self.discover_via_pod_labels())

        # Method 4: Environment variables or config
        discovered.extend(self.discover_via_env())

        # Deduplicate by service name and namespace
        seen_keys = set()
        unique = []
        for am in discovered:
            key = f"{am.get('namespace', 'unknown')}/{am.get('name', 'unknown')}"
            if key not in seen_keys:
                unique.append(am)
                seen_keys.add(key)

        logger.info(f"Discovered {len(unique)} AlertManager instance(s)")
        return unique

    async def discover_via_services(self) -> List[Dict[str, str]]:
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
                            discovered.append(
                                {
                                    "name": svc.metadata.name,
                                    "namespace": svc.metadata.namespace,
                                    "port": port,
                                    "source": "service",
                                    "use_proxy": self.use_proxy
                                    and self.kube_proxy
                                    and self.kube_proxy.available,
                                }
                            )
                            logger.info(
                                f"Found AlertManager service: {svc.metadata.name} in {svc.metadata.namespace}:{port}"
                            )
                        break
        except ApiException as e:
            logger.error(f"Failed to list services: {e}")

        return discovered

    async def discover_via_workloads(self) -> List[Dict[str, str]]:
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
                            {
                                "name": sts.metadata.name,
                                "namespace": sts.metadata.namespace,
                                "url": url,
                                "source": "statefulset",
                            }
                        )

            # Check Deployments
            deployments = self.apps_v1.list_deployment_for_all_namespaces()
            for dep in deployments.items:
                if self._is_alertmanager_workload(dep.metadata.name):
                    url = self._construct_url_from_workload(dep, "deployment")
                    if url:
                        discovered.append(
                            {
                                "name": dep.metadata.name,
                                "namespace": dep.metadata.namespace,
                                "url": url,
                                "source": "deployment",
                            }
                        )
        except ApiException as e:
            logger.error(f"Failed to list workloads: {e}")

        return discovered

    async def discover_via_pod_labels(self) -> List[Dict[str, str]]:
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
                                        {
                                            "name": pod.metadata.name,
                                            "namespace": pod.metadata.namespace,
                                            "url": url,
                                            "source": "pod",
                                        }
                                    )
                                    break
        except ApiException as e:
            logger.error(f"Failed to list pods: {e}")

        return discovered

    def discover_via_env(self) -> List[Dict[str, str]]:
        """Discover AlertManager via environment variables."""
        import os

        discovered = []

        # Check common environment variables
        alertmanager_url = os.getenv("ALERTMANAGER_URL")
        if alertmanager_url:
            discovered.append(
                {
                    "name": "env-configured",
                    "namespace": "unknown",
                    "url": alertmanager_url,
                    "source": "environment",
                }
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

    def _get_proxy_url(self, service_name: str, namespace: str, port: int) -> str:
        """Get the Kubernetes API proxy URL for a service."""
        # Try to get the API server URL from kubeconfig
        try:
            from kubernetes.client import Configuration

            config = Configuration.get_default_copy()
            host = config.host

            # Use the Kubernetes API proxy endpoint
            # This allows access to services from outside the cluster
            proxy_path = (
                f"/api/v1/namespaces/{namespace}/services/{service_name}:{port}/proxy"
            )
            return f"{host}{proxy_path}"
        except Exception as e:
            logger.debug(f"Could not build proxy URL: {e}")
            # Fallback to direct cluster URL (works only in-cluster)
            return f"http://{service_name}.{namespace}.svc.cluster.local:{port}"

    async def verify_alertmanager(self, url: str) -> bool:
        """Verify that an AlertManager instance is accessible."""
        try:
            # Special handling for proxy URLs
            if "/proxy" in url:
                # For proxy URLs, we need to use the kubeconfig auth
                from kubernetes.client import ApiClient

                api_client = ApiClient()

                # Make request with auth
                response = api_client.call_api(
                    f"{url}/api/v2/status",
                    "GET",
                    response_type="object",
                    _return_http_data_only=True,
                    _preload_content=False,
                )
                return True
            else:
                # Regular HTTP request
                response = requests.get(f"{url}/api/v2/status", timeout=5)
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Failed to verify AlertManager at {url}: {e}")
            return False
