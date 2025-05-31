import os
from typing import Dict, List

from pydantic import BaseModel

CUSTOM_TOOLSET_LOCATION = os.environ.get(
    "CUSTOM_TOOLSET_LOCATION", "/etc/holmes/config/custom_toolset.yaml"
)


class RobustaConfig(BaseModel):
    sinks_config: List[Dict[str, Dict]]
    global_config: dict
