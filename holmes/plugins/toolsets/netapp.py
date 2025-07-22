import logging
import requests
from typing import Dict, Any, Optional, Tuple

from pydantic import BaseModel

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.consts import TOOLSET_CONFIG_MISSING_ERROR
from kubernetes import client, config
import os

try:
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        config.load_incluster_config()
    else:
        config.load_kube_config()
except config.config_exception.ConfigException as e:
    logging.warning(f"Running without kube-config! e={e}")


class NetAppConfig(BaseModel):
    url: str
    username: str
    password: str


class NetAppToolset(Toolset):
    config: Optional[NetAppConfig] = None
    volumes: Dict[str, str] = {}

    def __init__(self):
        super().__init__(
            name="netapp",
            description="Toolset for interacting with NetApp volumes using the NetApp REST API.",
            experimental=True,
            docs_url="",
            icon_url="https://www.netapp.com/favicon.ico",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[InvestigatePVInNetApp(toolset=self), InvestigatePVCInNetApp(toolset=self)],
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            return False, TOOLSET_CONFIG_MISSING_ERROR

        try:
            self.config = NetAppConfig(**config)
            self.volumes = self._fetch_all_volumes()
            logging.warning(f"Fetched {self.volumes} NetApp volumes.")
            return True, ""
        except Exception as e:
            logging.exception("NetAppToolset failed during prerequisites.")
            return False, f"Failed to initialize NetApp toolset: {e}"

    def _fetch_all_volumes(self) -> Dict[str, str]:
        endpoint = f"{self.config.url}/api/storage/volumes"
        response = requests.get(
            endpoint,
            auth=(self.config.username, self.config.password),
            verify=False,
        )
        response.raise_for_status()
        volumes_data = response.json()
        return {
            volume["name"]: volume["uuid"]
            for volume in volumes_data.get("records", [])
            if "name" in volume and "uuid" in volume
        }

    def get_example_config(self) -> Dict[str, Any]:
        return {
            "url": "https://netapp-api.example.com",
            "username": "{{ env.NETAPP_USERNAME }}",
            "password": "{{ env.NETAPP_PASSWORD }}"
        }

class BaseNetappTool(Tool):
    toolset: "NetAppToolset"

    def query_netapp_volume(self, internal_name: str, params: Dict[str, Any]) -> StructuredToolResult:
        toolset: NetAppToolset = self.toolset
        matched_volume = None
        for name, uuid in toolset.volumes.items():
            if name == internal_name:
                matched_volume = (name, uuid)
                break

        if not matched_volume:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"No matching NetApp volume for internal name '{internal_name}'.",
                params=params
            )

        uuid = matched_volume[1]
        endpoint = f"{toolset.config.url}/api/storage/volumes/{uuid}"

        try:
            response = requests.get(
                endpoint,
                auth=(toolset.config.username, toolset.config.password),
                verify=False,
            )
            response.raise_for_status()
            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                output=response.json(),
                params=params
            )
        except requests.RequestException as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed NetApp API query: {e}",
                params=params
            )

    def get_netapp_volume_by_pv_name(self, pv_name: str, params: Dict[str, Any]) -> StructuredToolResult:
        core_v1 = client.CoreV1Api()
        try:
            pv = core_v1.read_persistent_volume(pv_name)
            internal_name = pv.spec.csi.volume_attributes.get('internalName')

            if not internal_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"No 'internalName' in PV {pv_name}'s CSI attributes.",
                    params=params
                )

            return self.query_netapp_volume(internal_name, params)

        except client.exceptions.ApiException as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Kubernetes API error: {e}",
                params=params
            )

class InvestigatePVCInNetApp(BaseNetappTool):
    def __init__(self, toolset: NetAppToolset):
        super().__init__(
            name="investigate_pvc_in_netapp",
            description="Investigate a Kubernetes PVC and find related NetApp volume information.",
            parameters={
                "namespace": ToolParameter(
                    description="Namespace of the PVC",
                    type="string",
                    required=True
                ),
                "pvc_name": ToolParameter(
                    description="Name of the PersistentVolumeClaim (PVC)",
                    type="string",
                    required=True
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        namespace = params["namespace"]
        pvc_name = params["pvc_name"]
        core_v1 = client.CoreV1Api()

        try:
            pvc = core_v1.read_namespaced_persistent_volume_claim(pvc_name, namespace)
            pv_name = pvc.spec.volume_name
            if not pv_name:
                return StructuredToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"No PersistentVolume bound to PVC {namespace}/{pvc_name}",
                    params=params
                )

            return self.get_netapp_volume_by_pv_name(pv_name, params)

        except client.exceptions.ApiException as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Kubernetes API error: {e}",
                params=params
            )

    def get_parameterized_one_liner(self, params: Dict[str, Any]) -> str:
        return f"Investigate PVC '{params['namespace']}/{params['pvc_name']}' in NetApp"


class InvestigatePVInNetApp(BaseNetappTool):
    def __init__(self, toolset: NetAppToolset):
        super().__init__(
            name="investigate_pv_in_netapp",
            description="Investigate a Kubernetes PersistentVolume and find related NetApp volume information.",
            parameters={
                "pv_name": ToolParameter(
                    description="Name of the PersistentVolume (PV)",
                    type="string",
                    required=True
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        pv_name = params["pv_name"]
        return self.get_netapp_volume_by_pv_name(pv_name, params)


    def get_parameterized_one_liner(self, params: Dict[str, Any]) -> str:
        return f"Investigate PV '{params['pv_name']}' in NetApp"
