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
        logging.info(f"Searching for NetApp volume with internal name: {internal_name}")

        matched_volume = None
        for name, uuid in toolset.volumes.items():
            if name == internal_name:
                matched_volume = (name, uuid)
                break

        if not matched_volume:
            available = list(toolset.volumes.keys())
            logging.warning(f"No match for internal name '{internal_name}'. Available NetApp volumes: {available}")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"No matching NetApp volume for internal name '{internal_name}'.",
                params=params
            )

        uuid = matched_volume[1]
        endpoint = f"{toolset.config.url}/api/storage/volumes/{uuid}"
        logging.info(f"Querying NetApp API at: {endpoint}")

        try:
            response = requests.get(
                endpoint,
                auth=(toolset.config.username, toolset.config.password),
                verify=False,
            )
            response.raise_for_status()
            data = response.json()
            logging.info(f"Full NetApp API response: {data}")

            formatted_output = self._format_netapp_volume(data)
            logging.info(f"Formatted NetApp volume output:\n{formatted_output}")

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                output=formatted_output,
                params=params,
                raw_output=data
            )
        except requests.RequestException as e:
            logging.exception("NetApp API query failed")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed NetApp API query: {e}",
                params=params
            )

    def _format_netapp_volume(self, data: Dict[str, Any]) -> str:
        try:
            size = self._human_readable_size(data.get('size', 0))
            space = data.get('space', {})

            return "\n".join([
                f"Volume Name: {data.get('name', 'N/A')}",
                f"UUID: {data.get('uuid', 'N/A')}",
                f"Created: {data.get('create_time', 'N/A')}",
                f"State: {data.get('state', 'N/A')}",
                f"Style: {data.get('style', 'N/A')}",
                f"Size: {size}",
                f"Used: {self._human_readable_size(space.get('used', 0))}",
                f"Available: {self._human_readable_size(space.get('available', 0))}",
                f"Aggregate: {data.get('aggregates', [{}])[0].get('name', 'N/A')}",
                f"SVM Name: {data.get('svm', {}).get('name', 'N/A')}",
                f"Snapshot Policy: {data.get('snapshot_policy', {}).get('name', 'N/A')}",
                f"Status Messages: {'; '.join(data.get('status', [])) if data.get('status') else 'None'}"
            ])
        except Exception as e:
            logging.exception("Failed to format NetApp volume data")
            return "Failed to format NetApp volume details"


    def _human_readable_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(min(len(size_name) - 1, (size_bytes.bit_length() - 1) // 10))
        p = 1 << (i * 10)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"


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
