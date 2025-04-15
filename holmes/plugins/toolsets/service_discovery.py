import logging
from kubernetes import client
from kubernetes.client import V1ServiceList
from kubernetes.client.models.v1_service import V1Service
import os
from cachetools import TTLCache
from typing import List, Optional

SERVICE_CACHE_TTL_SEC = int(os.environ.get("SERVICE_CACHE_TTL_SEC", 900))

CLUSTER_DOMAIN = os.environ.get("CLUSTER_DOMAIN", "cluster.local")


def find_service_url(label_selector):
    """
    Get the url of an in-cluster service with a specific label
    """
    # we do it this way because there is a weird issue with hikaru's ServiceList.listServiceForAllNamespaces()
    v1 = client.CoreV1Api()
    svc_list: V1ServiceList = v1.list_service_for_all_namespaces(
        label_selector=label_selector
    )
    if not svc_list.items:
        return None
    svc: V1Service = svc_list.items[0]
    name = svc.metadata.name
    namespace = svc.metadata.namespace
    port = svc.spec.ports[0].port
    url = f"http://{name}.{namespace}.svc.{CLUSTER_DOMAIN}:{port}"
    logging.info(
        f"discovered service with label-selector: `{label_selector}` at url: `{url}`"
    )
    return url


class ServiceDiscovery:
    cache: TTLCache = TTLCache(maxsize=5, ttl=SERVICE_CACHE_TTL_SEC)

    @classmethod
    def find_url(cls, selectors: List[str], error_msg: str) -> Optional[str]:
        """
        Try to autodiscover the url of an in-cluster service
        """
        cache_key = ",".join(selectors)
        cached_value = cls.cache.get(cache_key)
        if cached_value:
            return cached_value

        for label_selector in selectors:
            service_url = find_service_url(label_selector)
            if service_url:
                cls.cache[cache_key] = service_url
                return service_url

        logging.debug(error_msg)
        return None


class PrometheusDiscovery(ServiceDiscovery):
    @classmethod
    def find_prometheus_url(cls) -> Optional[str]:
        return super().find_url(
            selectors=[
                "app=kube-prometheus-stack-prometheus",
                "app=prometheus,component=server,release!=kubecost",
                "app=prometheus-server",
                "app=prometheus-operator-prometheus",
                "app=rancher-monitoring-prometheus",
                "app=prometheus-prometheus",
                "app.kubernetes.io/component=query,app.kubernetes.io/name=thanos",
                "app.kubernetes.io/name=thanos-query",
                "app=thanos-query",
                "app=thanos-querier",
            ],
            error_msg="Prometheus url could not be found. Add 'prometheus_url' under your prometheus tools config",
        )

    @classmethod
    def find_vm_url(cls) -> Optional[str]:
        return super().find_url(
            selectors=[
                "app.kubernetes.io/name=vmsingle",
                "app.kubernetes.io/name=victoria-metrics-single",
                "app.kubernetes.io/name=vmselect",
                "app=vmselect",
            ],
            error_msg="Victoria Metrics url could not be found. Add 'prometheus_url' under your prometheus tools config",
        )
