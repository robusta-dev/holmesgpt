"""Kubernetes API proxy for accessing in-cluster services."""

import logging
from typing import Optional, Dict, Any
import requests  # type: ignore
from kubernetes import client
from holmes.alert_proxy.kube_config_singleton import KubeConfigSingleton

logger = logging.getLogger(__name__)


class KubeProxy:
    """Access Kubernetes services via API proxy."""

    def __init__(self, kubeconfig_path: Optional[str] = None):
        """Initialize with Kubernetes client."""
        # Use singleton for Kubernetes configuration
        self.kube_config = KubeConfigSingleton()
        self.available = self.kube_config.initialize(kubeconfig_path)

        if self.available:
            self.api_client = self.kube_config.api_client
            self.v1 = client.CoreV1Api(self.api_client) if self.api_client else None
        else:
            self.api_client = None
            self.v1 = None
            self.api_host = None
            self.headers: Dict[str, str] = {}
            self.cert = None
            self.ca_cert = None
            self.verify_ssl = True
            return

        try:
            # Get the API server URL and auth headers
            assert self.api_client is not None
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

    def proxy_request(
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

        # Configure SSL for requests library
        verify_param = False  # Default to no verification
        cert_param = None

        if self.verify_ssl and self.ca_cert:
            # Use CA cert file for verification
            verify_param = self.ca_cert
        elif not self.verify_ssl:
            # Disable SSL verification
            verify_param = False

        # Handle client certificate if provided
        if self.cert:
            cert_param = self.cert

        # Make the request via API proxy
        try:
            logger.debug(f"Making proxy request to {url}")
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                verify=verify_param,
                cert=cert_param,
                timeout=10,
                **kwargs,
            )
            if response.status_code == 200:
                data = response.json()
                logger.debug(
                    f"Proxy request successful, got {len(data) if isinstance(data, list) else 'dict'} items"
                )
                return data
            elif response.status_code == 503:
                # Service unavailable - likely no endpoints/pods
                logger.warning(
                    f"Service {service_name} has no available endpoints (503)"
                )
                return {}  # Return empty dict instead of None
            else:
                logger.warning(
                    f"Proxy request failed for {service_name} ({response.status_code}): {response.text[:200]}"
                )
                return {}  # Return empty dict instead of None

        except Exception as e:
            logger.error(f"Error making proxy request to {service_name}: {e}")
            return {}

    def get_alertmanager_alerts(
        self, service_name: str, namespace: str, port: int = 9093
    ) -> Optional[Dict[str, Any]]:
        """Get alerts from AlertManager via Kubernetes API proxy."""
        result = self.proxy_request(
            service_name=service_name,
            namespace=namespace,
            port=port,
            path="/api/v2/alerts",
        )
        # Return None for empty dict to make it clearer
        return result if result and result != {} else None

    def verify_alertmanager(
        self, service_name: str, namespace: str, port: int = 9093
    ) -> bool:
        """Verify AlertManager is accessible via proxy."""
        try:
            result = self.proxy_request(
                service_name=service_name,
                namespace=namespace,
                port=port,
                path="/api/v2/status",
            )
            return result is not None
        except Exception as e:
            logger.debug(f"Failed to verify AlertManager {service_name}: {e}")
            return False
