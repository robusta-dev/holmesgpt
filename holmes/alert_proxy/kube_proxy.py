"""Kubernetes API proxy for accessing in-cluster services."""

import logging
from typing import Optional, Dict, Any
import aiohttp
from kubernetes import client, config as k8s_config

logger = logging.getLogger(__name__)


class KubeProxy:
    """Access Kubernetes services via API proxy."""

    def __init__(self, kubeconfig_path: Optional[str] = None):
        """Initialize with Kubernetes client."""
        try:
            if kubeconfig_path:
                k8s_config.load_kube_config(config_file=kubeconfig_path)
            else:
                # Try in-cluster config first, then default kubeconfig
                try:
                    k8s_config.load_incluster_config()
                    logger.info("Using in-cluster Kubernetes config")
                except Exception:
                    k8s_config.load_kube_config()
                    logger.info("Using kubeconfig")

            self.api_client = client.ApiClient()
            self.v1 = client.CoreV1Api(self.api_client)
            self.available = True

            # Get the API server URL and auth headers
            config = self.api_client.configuration
            self.api_host = config.host
            self.headers = {}

            # Add authentication headers
            if config.api_key:
                for key, value in config.api_key.items():
                    if key == "authorization":
                        self.headers["Authorization"] = value

            if config.cert_file:
                self.cert = config.cert_file
            else:
                self.cert = None

            if config.ssl_ca_cert:
                self.ca_cert = config.ssl_ca_cert
            else:
                self.ca_cert = None

            # Whether to verify SSL
            self.verify_ssl = (
                config.verify_ssl if hasattr(config, "verify_ssl") else True
            )

        except Exception as e:
            logger.warning(f"Kubernetes API not available: {e}")
            self.available = False

    def get_service_proxy_url(
        self, service_name: str, namespace: str, port: int
    ) -> str:
        """Get the Kubernetes API proxy URL for a service."""
        # Use the services proxy endpoint
        # Format: /api/v1/namespaces/{namespace}/services/{service}:{port}/proxy
        proxy_path = (
            f"/api/v1/namespaces/{namespace}/services/{service_name}:{port}/proxy"
        )
        return f"{self.api_host}{proxy_path}"

    async def proxy_request(
        self,
        service_name: str,
        namespace: str,
        port: int,
        path: str = "",
        method: str = "GET",
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a request to a service via Kubernetes API proxy."""
        if not self.available:
            raise RuntimeError("Kubernetes API not available")

        # Build the full proxy URL
        base_url = self.get_service_proxy_url(service_name, namespace, port)

        # Remove leading slash from path if present
        if path and path.startswith("/"):
            path = path[1:]

        url = f"{base_url}/{path}" if path else base_url

        # Configure SSL
        ssl_context = None
        if not self.verify_ssl:
            import ssl

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        elif self.ca_cert:
            import ssl

            ssl_context = ssl.create_default_context(cafile=self.ca_cert)
            if self.cert:
                ssl_context.load_cert_chain(self.cert)

        # Make the request via API proxy
        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    ssl=ssl_context if ssl_context else False,
                    **kwargs,
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 503:
                        # Service unavailable - likely no endpoints/pods
                        logger.debug(
                            f"Service {service_name} has no available endpoints"
                        )
                        return {}  # Return empty dict instead of None
                    else:
                        text = await response.text()
                        logger.warning(
                            f"Proxy request failed for {service_name} ({response.status}): {text}"
                        )
                        return {}  # Return empty dict instead of None

            except Exception as e:
                logger.error(f"Error making proxy request to {service_name}: {e}")
                return {}

    async def get_alertmanager_alerts(
        self, service_name: str, namespace: str, port: int = 9093
    ) -> Optional[Dict[str, Any]]:
        """Get alerts from AlertManager via Kubernetes API proxy."""
        return await self.proxy_request(
            service_name=service_name,
            namespace=namespace,
            port=port,
            path="/api/v2/alerts",
        )

    async def verify_alertmanager(
        self, service_name: str, namespace: str, port: int = 9093
    ) -> bool:
        """Verify AlertManager is accessible via proxy."""
        try:
            result = await self.proxy_request(
                service_name=service_name,
                namespace=namespace,
                port=port,
                path="/api/v2/status",
            )
            return result is not None
        except Exception as e:
            logger.debug(f"Failed to verify AlertManager {service_name}: {e}")
            return False
