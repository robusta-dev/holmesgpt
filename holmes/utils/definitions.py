import os
from typing import Dict, List

from pydantic import BaseModel

# Directory for custom toolsets (all .yaml files will be loaded)
CUSTOM_TOOLSET_DIR = os.environ.get(
    "CUSTOM_TOOLSET_DIR", os.path.expanduser("~/.holmes/custom_toolsets")
)


class RobustaConfig(BaseModel):
    sinks_config: List[Dict[str, Dict]]
    global_config: dict
