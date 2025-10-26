import os
from typing import Dict, List

from pydantic import BaseModel


HOLMES_CONFIG_LOCATION_ = os.environ.get(
    "HOLMES_CONFIG_LOCATION", "/etc/holmes/config/holmes_config.yaml"
)
CUSTOM_TOOLSET_LOCATION = os.environ.get(
    "CUSTOM_TOOLSET_LOCATION", "/etc/holmes/config/custom_toolset.yaml"
)


class RobustaConfig(BaseModel):
    sinks_config: List[Dict[str, Dict]]
    global_config: dict
