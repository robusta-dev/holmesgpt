from typing import Dict, List

from pydantic import BaseModel


class RobustaConfig(BaseModel):
    sinks_config: List[Dict[str, Dict]]
    global_config: dict
