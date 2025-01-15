import logging
import os
import os.path
from typing import List, Optional

from holmes.core.supabase_dal import SupabaseDal
from holmes.plugins.toolsets.findings import FindingsToolset
from holmes.plugins.toolsets.grafana.common import GrafanaConfig
from holmes.plugins.toolsets.grafana.toolset_grafana_loki import GrafanaLokiToolset
from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import GrafanaTempoToolset
from holmes.plugins.toolsets.internet import InternetToolset
from pydantic import BaseModel

from holmes.core.tools import Toolset, YAMLToolset
from typing import Dict
import yaml

THIS_DIR = os.path.abspath(os.path.dirname(__file__))

class ToolsetsYaml(BaseModel):
    toolsets: Dict[str, YAMLToolset]

def load_toolsets_from_file(path: str, silent_fail: bool = False) -> List[YAMLToolset]:
    file_toolsets = []
    with open(path) as file:
        parsed_yaml = yaml.safe_load(file)
        toolsets = parsed_yaml.get("toolsets", {})
        for name, config in toolsets.items():
            try:
                toolset = YAMLToolset(**config, name=name)
                toolset.set_path(path)
                file_toolsets.append(YAMLToolset(**config, name=name))
            except Exception:
                if not silent_fail:
                    logging.error(f"Error happened while loading {name} toolset from {path}",
                                  exc_info=True)

    return file_toolsets

def load_python_toolsets(dal:Optional[SupabaseDal], grafana_config:Optional[GrafanaConfig]) -> List[Toolset]:
    logging.debug("loading python toolsets")
    if not grafana_config:
        # passing an empty config simplifies the downstream code
        grafana_config = GrafanaConfig()

    return [InternetToolset(), FindingsToolset(dal), GrafanaLokiToolset(grafana_config), GrafanaTempoToolset(grafana_config)]

def load_builtin_toolsets(dal:Optional[SupabaseDal] = None, grafana_config:Optional[GrafanaConfig] = GrafanaConfig()) -> List[Toolset]:
    all_toolsets = []
    logging.debug(f"loading toolsets from {THIS_DIR}")
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        all_toolsets.extend(load_toolsets_from_file(path))

    all_toolsets.extend(load_python_toolsets(dal, grafana_config))
    return all_toolsets
