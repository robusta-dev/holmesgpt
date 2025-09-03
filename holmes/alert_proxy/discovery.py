"""Service discovery for AlertManager instances."""

import logging
import os
import re
from typing import List, Optional

from kubernetes import client
from kubernetes.client.rest import ApiException
from holmes.alert_proxy.kube_proxy import KubeProxy
from holmes.alert_proxy.kube_config_singleton import KubeConfigSingleton
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

        # Use singleton for Kubernetes configuration (KubeProxy already initialized it)
        self.kube_config = KubeConfigSingleton()
        # Just call initialize to ensure it's set up (it won't log again if already initialized)
        self.k8s_available = self.kube_config.initialize(kubeconfig_path)

        if self.k8s_available:
            api_client = self.kube_config.api_client
            self.v1 = client.CoreV1Api(api_client) if api_client else None
        else:
            self.v1 = None

    def discover_all(self) -> List[AlertManagerInstance]:
        """Discover all AlertManager instances using multiple methods."""
        discovered = []

        if self.k8s_available:
            logger.info("Starting AlertManager discovery via multiple methods...")

            # Method 1: Service discovery
            services = self.discover_via_services()
            logger.info(f"  Service discovery found: {len(services)} instance(s)")
            for svc in services:
                logger.info(
                    f"    - {svc.namespace}/{svc.name} (port: {svc.port}, proxy: {svc.use_proxy})"
                )
            discovered.extend(services)

            # Skip workload and pod discovery - services are sufficient
            # Direct workload/pod connections cause issues from outside the cluster
            logger.info("  Skipping workload and pod discovery (using services only)")
        else:
            logger.warning("Kubernetes not available, skipping k8s-based discovery")

        # Method 4: Environment variables or config
        env_instances = self.discover_via_env()
        if env_instances:
            logger.info(
                f"  Environment discovery found: {len(env_instances)} instance(s)"
            )
            for env in env_instances:
                logger.info(f"    - {env.name} (url: {env.url})")
            discovered.extend(env_instances)

        # Simple deduplication by namespace/name
        seen_keys = set()
        unique = []
        for am in discovered:
            key = f"{am.namespace}/{am.name}"
            if key not in seen_keys:
                unique.append(am)
                seen_keys.add(key)
            else:
                logger.debug(f"  Skipping duplicate: {key}")

        logger.info(
            f"Discovery complete: {len(unique)} unique AlertManager instance(s) found"
        )
        return unique

    def discover_via_services(self) -> List[AlertManagerInstance]:
        """Discover AlertManager via Kubernetes services."""
        discovered = []

        try:
            assert self.v1 is not None
            services = self.v1.list_service_for_all_namespaces()

            for svc in services.items:
                # Check if service name matches AlertManager patterns
                for pattern in self.ALERTMANAGER_PATTERNS:
                    if re.match(pattern, svc.metadata.name, re.IGNORECASE):
                        # Check if service has ready endpoints (backing pods)
                        try:
                            assert self.v1 is not None
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
                            logger.debug(
                                f"Found AlertManager service: {svc.metadata.name} in {svc.metadata.namespace}:{port}"
                            )
                        break
        except ApiException as e:
            logger.error(f"Failed to list services: {e}")

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
                assert self.v1 is not None
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
                                            port=port.container_port,
                                            source="pod",
                                            use_proxy=False,  # Don't use proxy for direct pod IPs
                                        )
                                    )
                                    logger.info(
                                        f"Found AlertManager pod: {pod.metadata.name} at {pod.status.pod_ip}:{port.container_port}"
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
                    name="ALERTMANAGER_URL-env-var",
                    namespace="from-env",
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
