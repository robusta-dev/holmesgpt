import logging
from typing import List, Optional
import requests  # type: ignore
from functools import cache
from pydantic import BaseModel, ConfigDict
from holmes.common.env_vars import ROBUSTA_API_ENDPOINT

HOLMES_GET_INFO_URL = f"{ROBUSTA_API_ENDPOINT}/api/holmes/get_info"
TIMEOUT = 0.5


class HolmesInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    latest_version: Optional[str] = None


class RobustaModelsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    models: List[str]
    default_model: Optional[str] = None


@cache
def fetch_robusta_models(
    account_id: str, token: str
) -> Optional[RobustaModelsResponse]:
    try:
        session_request = {"session_token": token, "account_id": account_id}
        resp = requests.post(
            f"{ROBUSTA_API_ENDPOINT}/api/llm/models",
            json=session_request,
            timeout=10,
        )
        resp.raise_for_status()
        response_json = resp.json()
        return RobustaModelsResponse(**response_json)
    except Exception:
        logging.exception("Failed to fetch robusta models")
        return None


@cache
def fetch_holmes_info() -> Optional[HolmesInfo]:
    try:
        response = requests.get(HOLMES_GET_INFO_URL, timeout=TIMEOUT)
        response.raise_for_status()
        result = response.json()
        return HolmesInfo(**result)
    except Exception:
        return None
