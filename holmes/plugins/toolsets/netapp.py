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
            tools=[NetAppGetVolumeDetails(toolset=self)],
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

class NetAppGetVolumeDetails(Tool):
    toolset: "NetAppToolset"

    def __init__(self, toolset: NetAppToolset):
        self.toolset=toolset
        super().__init__(
            name="get_netapp_volume_details",
            description="Fetch detailed information for a NetApp volume using its name.",
            parameters={
                "volume_name": ToolParameter(
                    description="Name of the NetApp volume",
                    type="string",
                    required=True,
                )
            },
        )

    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        volume_name = params.get("volume_name")
        toolset: NetAppToolset = self.toolset

        if not toolset.config:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error="NetApp toolset is not configured.",
                params=params,
            )

        uuid = toolset.volumes.get(volume_name)
        if not uuid:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Volume name '{volume_name}' not found in NetApp volumes.",
                params=params,
            )

        endpoint = f"{toolset.config.url}/api/storage/volumes/{uuid}"
        try:
            response = requests.get(
                endpoint,
                auth=(toolset.config.username, toolset.config.password),
                verify=False,
            )
            response.raise_for_status()
            volume_data = response.json()

            formatted_output = self._format_volume_info(volume_data)

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                output=formatted_output,
                params=params,
                raw_output=volume_data,
            )
        except requests.RequestException as e:
            logging.exception("Failed to fetch NetApp volume details")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=str(e),
                params=params,
            )

    def _format_volume_info(self, data: Dict[str, Any]) -> str:
        lines = [
            f"Volume Name: {data.get('name')}",
            f"UUID: {data.get('uuid')}",
            f"Created On: {data.get('create_time')}",
            f"Size: {self._human_readable_size(data.get('size', 0))}",
            f"Used Space: {self._human_readable_size(data.get('space', {}).get('used', 0))}",
            f"Available Space: {self._human_readable_size(data.get('space', {}).get('available', 0))}",
            f"State: {data.get('state')}",
            f"Style: {data.get('style')}",
            f"Snapshot Policy: {data.get('snapshot_policy', {}).get('name')}",
            f"Aggregate: {data.get('aggregates', [{}])[0].get('name', 'N/A')}",
            f"SVM Name: {data.get('svm', {}).get('name', 'N/A')}",
            f"Status Messages: {'; '.join(data.get('status', [])) if data.get('status') else 'None'}",
        ]
        return "\n".join(lines)

    def _human_readable_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(min(len(size_name) - 1, (size_bytes.bit_length() - 1) // 10))
        p = 1 << (i * 10)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def get_parameterized_one_liner(self, params: Dict[str, Any]) -> str:
        return f"Get NetApp volume details for volume: {params.get('volume_name', 'UNKNOWN')}"
