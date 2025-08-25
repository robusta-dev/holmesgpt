"""Singleton for Kubernetes configuration to avoid multiple initializations."""

import logging
from typing import Optional
from kubernetes import client, config as k8s_config

logger = logging.getLogger(__name__)


class KubeConfigSingleton:
    """Singleton to manage Kubernetes configuration."""

    _instance = None
    _initialized = False
    _api_client: Optional[client.ApiClient] = None
    _available = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, kubeconfig_path: Optional[str] = None) -> bool:
        """Initialize Kubernetes configuration once.

        Returns:
            True if Kubernetes is available, False otherwise
        """
        if self._initialized:
            return self._available

        try:
            if kubeconfig_path:
                k8s_config.load_kube_config(config_file=kubeconfig_path)
                logger.info(f"Using kubeconfig from {kubeconfig_path}")
            else:
                # Try in-cluster config first, then default kubeconfig
                try:
                    k8s_config.load_incluster_config()
                    logger.info("Using in-cluster Kubernetes config")
                except Exception:
                    k8s_config.load_kube_config()
                    logger.info("Using kubeconfig")

            self._api_client = client.ApiClient()
            self._available = True
            self._initialized = True

        except Exception as e:
            logger.warning(f"Kubernetes API not available: {e}")
            self._available = False
            self._initialized = True

        return self._available

    @property
    def api_client(self) -> Optional[client.ApiClient]:
        """Get the shared API client."""
        if not self._initialized:
            self.initialize()
        return self._api_client

    @property
    def available(self) -> bool:
        """Check if Kubernetes is available."""
        if not self._initialized:
            self.initialize()
        return self._available

    def reset(self):
        """Reset the singleton (mainly for testing)."""
        self._initialized = False
        self._api_client = None
        self._available = False
