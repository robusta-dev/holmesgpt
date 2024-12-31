import logging
import os
import os.path
from typing import List, Optional

from opensearchpy.helpers.signer import Dict

from holmes.core.supabase_dal import SupabaseDal
from holmes.plugins.toolsets.findings import FindingsToolset
from holmes.plugins.toolsets.internet import InternetToolset
from pydantic import BaseModel

from holmes.core.tools import Toolset, YAMLToolset
from holmes.plugins.toolsets.opensearch import OpenSearchToolset
from typing import Dict
from pydantic import BaseModel
from typing import Optional
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
            except Exception as e:
                if not silent_fail:
                    logging.error(f"Error happened while loading {name} toolset from {path}",
                                  exc_info=True)

    return file_toolsets


def load_python_toolsets(dal:Optional[SupabaseDal], opensearch_clusters:Optional[List[Dict]]) -> List[Toolset]:
    logging.debug("loading python toolsets")
    toolsets = [InternetToolset(), FindingsToolset(dal)]
    if opensearch_clusters and len(opensearch_clusters) > 0:
        opensearch = OpenSearchToolset(clusters_configs=opensearch_clusters)
        toolsets.append(opensearch)
    return toolsets


def load_builtin_toolsets(dal:Optional[SupabaseDal] = None, opensearch_clusters:Optional[List[Dict]] = []) -> List[Toolset]:
    all_toolsets = []
    logging.debug(f"loading toolsets from {THIS_DIR}")
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        all_toolsets.extend(load_toolsets_from_file(path))

    all_toolsets.extend(load_python_toolsets(dal=dal, opensearch_clusters=opensearch_clusters))
    return all_toolsets
