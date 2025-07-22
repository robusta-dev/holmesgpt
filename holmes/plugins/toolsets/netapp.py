import logging
import os
import requests
from typing import Dict, Any, Optional

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)


class NetAppToolset(Toolset):
    def __init__(self):
        self.netapp_url: Optional[str] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.volumes: Dict[str, str] = {}  # name -> uuid mapping

        super().__init__(
            name="netapp",
            enabled=False,
            description="Toolset for interacting with NetApp volumes in the cluster using NetApp REST APIs.",
            docs_url="",
            icon_url="https://www.netapp.com/favicon.ico",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[NetAppGetVolumeDetails(self)],
            tags=[ToolsetTag.INTEGRATIONS],
            is_default=False,
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> tuple[bool, str]:
        try:
            self.netapp_url = config.get("url")
            self.username = config.get("username")
            self.password = config.get("password")

            if not all([self.netapp_url, self.username, self.password]):
                return False, "Missing NetApp configuration: 'url', 'username', and 'password' are required."

            self.volumes = self._fetch_all_volumes()
            return True, f"Loaded {len(self.volumes)} NetApp volumes."

        except Exception as e:
            logging.exception("NetAppToolset initialization failed.")
            return False, str(e)

    def _fetch_all_volumes(self) -> Dict[str, str]:
        endpoint = f"{self.netapp_url}/api/storage/volumes"
        response = requests.get(
            endpoint,
            auth=(self.username, self.password),
            verify=False
        )
        response.raise_for_status()
        volumes_data = response.json()
        # Map volume name to UUID
        return {
            volume['name']: volume['uuid']
            for volume in volumes_data.get('records', [])
            if 'name' in volume and 'uuid' in volume
        }
        
    def get_example_config(self) -> Dict[str, Any]:
        return {}

class NetAppGetVolumeDetails(Tool):
    def __init__(self, toolset: NetAppToolset):
        super().__init__(
            name="get_netapp_volume_details",
            description="Fetch detailed information for a NetApp volume given its name.",
            parameters={
                "volume_name": ToolParameter(
                    description="Name of the NetApp volume to query.",
                    type="string",
                    required=True,
                )
            },
            toolset=toolset,
        )

    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        volume_name = params.get("volume_name")
        toolset: NetAppToolset = self.toolset

        uuid = toolset.volumes.get(volume_name)
        if not uuid:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Volume name '{volume_name}' not found in NetApp volumes.",
                params=params
            )

        endpoint = f"{toolset.netapp_url}/api/storage/volumes/{uuid}"
        try:
            response = requests.get(
                endpoint,
                auth=(toolset.username, toolset.password),
                verify=False
            )
            response.raise_for_status()
            volume_data = response.json()

            formatted_output = self._format_volume_info(volume_data)

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS,
                output=formatted_output,
                params=params,
                raw_output=volume_data
            )

        except requests.RequestException as e:
            logging.exception("Failed to fetch volume details from NetApp API")
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=str(e),
                params=params
            )

    def _format_volume_info(self, data: Dict[str, Any]) -> str:
        lines = [
            f"**Volume Name:** {data.get('name')}",
            f"**UUID:** {data.get('uuid')}",
            f"**Created On:** {data.get('create_time')}",
            f"**Size:** {self._human_readable_size(data.get('size', 0))}",
            f"**Used Space:** {self._human_readable_size(data.get('space', {}).get('used', 0))}",
            f"**Available Space:** {self._human_readable_size(data.get('space', {}).get('available', 0))}",
            f"**State:** {data.get('state')}",
            f"**Style:** {data.get('style')}",
            f"**Snapshot Policy:** {data.get('snapshot_policy', {}).get('name')}",
            f"**Aggregate:** {data.get('aggregates', [{}])[0].get('name', 'N/A')}",
            f"**SVM Name:** {data.get('svm', {}).get('name', 'N/A')}",
            f"**Status Messages:** {'; '.join(data.get('status', [])) if data.get('status') else 'None'}"
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
        return f"Get NetApp volume details for volume name: {params.get('volume_name', 'UNKNOWN')}"

