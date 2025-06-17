import logging
from typing import List, Optional
import requests  # type: ignore
from pydantic import BaseModel, ConfigDict
from holmes.common.env_vars import ROBUSTA_API_ENDPOINT

HOLMES_GET_INFO_URL = f"{ROBUSTA_API_ENDPOINT}/api/holmes/get_info"
HOLMES_TOOLSET_CONFIG_URL = f"{ROBUSTA_API_ENDPOINT}/api/holmes/toolset_configs"

TIMEOUT = 2


class HolmesInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    latest_version: Optional[str] = None


def fetch_holmes_info() -> Optional[HolmesInfo]:
    try:
        response = requests.get(HOLMES_GET_INFO_URL, timeout=TIMEOUT)
        response.raise_for_status()
        result = response.json()
        return HolmesInfo(**result)
    except Exception:
        logging.info("Failed to fetch holmes info")
        return None


class HolmesToolsetConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    account_id: str
    cluster_id: str
    config: Optional[dict] = None
    enabled: bool
    id: str
    toolset_name: str
    toolset_version: Optional[str] = None


def fetch_holmes_toolset_config(
    session_token: str, account_id: str, cluster_id: str
) -> List[HolmesToolsetConfig]:
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            HOLMES_TOOLSET_CONFIG_URL,
            timeout=30,
            headers=headers,
            params={"account_id": account_id, "cluster_id": cluster_id},
        )
        response.raise_for_status()
        result = response.json()

        toolset_configs: List[HolmesToolsetConfig] = [
            HolmesToolsetConfig(**item) for item in result["configs"]
        ]
        return toolset_configs
    except Exception:
        logging.exception("Failed to fetch holmes toolset configs")
        return []
