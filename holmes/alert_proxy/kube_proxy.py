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
            logger.warning("KubeProxy: Kubernetes not available, proxy disabled")
            return

        try:
            # Get the API server URL and auth headers
            assert self.api_client is not None
            config = self.api_client.configuration
            self.api_host = config.host
            self.headers = {}

            logger.info(f"KubeProxy: API host: {self.api_host}")

            # Add authentication headers
            if config.api_key:
                for key, value in config.api_key.items():
                    if key == "authorization":
                        self.headers["Authorization"] = value
                        logger.info(f"KubeProxy: Using API key auth (key type: {key})")

            # Handle client certificate - requests library needs both cert and key
            if config.cert_file:
                # Check if we have both cert and key files
                if hasattr(config, "key_file") and config.key_file:
                    # requests library expects a tuple of (cert_file, key_file) for client certs
                    self.cert = (config.cert_file, config.key_file)
                    logger.info(
                        f"KubeProxy: Client cert/key configured: {config.cert_file}, {config.key_file}"
                    )
                else:
                    # Only cert file, no separate key file (might be combined in the cert file)
                    self.cert = config.cert_file
                    logger.info(
                        f"KubeProxy: Client cert configured (no separate key): {config.cert_file}"
                    )

                # Validate cert file exists and is readable
                try:
                    import os

                    if isinstance(self.cert, tuple):
                        for cert_path in self.cert:
                            if not os.path.exists(cert_path):
                                logger.error(
                                    f"KubeProxy: Certificate file not found: {cert_path}"
                                )
                                self.cert = None
                    elif self.cert and not os.path.exists(self.cert):
                        logger.error(
                            f"KubeProxy: Certificate file not found: {self.cert}"
                        )
                        self.cert = None
                except Exception as e:
                    logger.error(f"KubeProxy: Error checking cert files: {e}")
                    self.cert = None
            else:
                self.cert = None
                logger.info("KubeProxy: No client cert configured")

            if config.ssl_ca_cert:
                self.ca_cert = config.ssl_ca_cert
                logger.info(f"KubeProxy: CA cert configured: {config.ssl_ca_cert}")
                # Validate CA cert file exists
                try:
                    import os

                    if not os.path.exists(self.ca_cert):
                        logger.error(
                            f"KubeProxy: CA cert file not found: {self.ca_cert}"
                        )
                        self.ca_cert = None
                except Exception as e:
                    logger.error(f"KubeProxy: Error checking CA cert file: {e}")
            else:
                self.ca_cert = None
                logger.info("KubeProxy: No CA cert configured")

            # Whether to verify SSL
            self.verify_ssl = (
                config.verify_ssl if hasattr(config, "verify_ssl") else True
            )
            logger.info(f"KubeProxy: SSL verification: {self.verify_ssl}")

        except Exception as e:
            logger.warning(f"KubeProxy: Kubernetes API not available: {e}")
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

        logger.info("KubeProxy: Configuring SSL for proxy request")
        logger.info(
            f"  verify_ssl={self.verify_ssl}, ca_cert={self.ca_cert}, cert={self.cert}"
        )

        if self.verify_ssl and self.ca_cert:
            # Use CA cert file for verification
            verify_param = self.ca_cert
            logger.info(f"  Using CA cert for SSL verification: {self.ca_cert}")
        elif not self.verify_ssl:
            # Disable SSL verification
            verify_param = False
            logger.info("  SSL verification disabled")

        # Handle client certificate if provided (only when SSL verification is enabled)
        if self.cert and self.verify_ssl:
            cert_param = self.cert
            logger.info(f"  Using client cert: {self.cert}")

        # Make the request via API proxy
        try:
            logger.info(f"Making proxy request to {url}")
            logger.info(f"  Headers: {list(self.headers.keys())}")
            logger.info(f"  Verify: {verify_param}")
            logger.info(f"  Cert: {cert_param}")

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

        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error making proxy request to {service_name}: {e}")
            logger.info(f"  SSL Error details: {str(e)}")
            logger.info(f"  URL: {url}")
            logger.info(f"  verify_param: {verify_param}")
            logger.info(f"  cert_param: {cert_param}")
            # Try to provide more helpful error messages
            if "PEM lib" in str(e):
                logger.error(
                    "  This appears to be a certificate format issue. Check that cert files are valid PEM format."
                )
            elif "certificate verify failed" in str(e):
                logger.error(
                    "  Certificate verification failed. The CA cert may not match the server's certificate."
                )
            return {}
        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"Connection Error making proxy request to {service_name}: {e}"
            )
            return {}
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout making proxy request to {service_name}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error making proxy request to {service_name}: {e}")
            import traceback

            logger.debug(f"  Traceback: {traceback.format_exc()}")
            return {}

    def get_alertmanager_alerts(
        self, service_name: str, namespace: str, port: int = 9093, subpath: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Get alerts from AlertManager via Kubernetes API proxy."""
        # Construct the path with optional subpath (e.g., "/alertmanager/api/v2/alerts" for Mimir)
        if subpath:
            # Ensure subpath starts with / and doesn't end with /
            if not subpath.startswith("/"):
                subpath = "/" + subpath
            if subpath.endswith("/"):
                subpath = subpath[:-1]
            path = f"{subpath}/api/v2/alerts"
        else:
            path = "/api/v2/alerts"

        result = self.proxy_request(
            service_name=service_name,
            namespace=namespace,
            port=port,
            path=path,
        )
        # Return None for empty dict to make it clearer
        return result if result and result != {} else None

    def verify_alertmanager(
        self, service_name: str, namespace: str, port: int = 9093, subpath: str = ""
    ) -> bool:
        """Verify AlertManager is accessible via proxy."""
        try:
            # Construct the path with optional subpath
            if subpath:
                # Ensure subpath starts with / and doesn't end with /
                if not subpath.startswith("/"):
                    subpath = "/" + subpath
                if subpath.endswith("/"):
                    subpath = subpath[:-1]
                path = f"{subpath}/api/v2/status"
            else:
                path = "/api/v2/status"

            result = self.proxy_request(
                service_name=service_name,
                namespace=namespace,
                port=port,
                path=path,
            )
            return result is not None
        except Exception as e:
            logger.debug(f"Failed to verify AlertManager {service_name}: {e}")
            return False
