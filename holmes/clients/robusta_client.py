import logging
from typing import Optional
import requests  # type: ignore
from pydantic import BaseModel, ConfigDict
from holmes.common.env_vars import ROBUSTA_API_ENDPOINT

HOLMES_GET_INFO_URL = f"{ROBUSTA_API_ENDPOINT}/api/holmes/get_info"
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
