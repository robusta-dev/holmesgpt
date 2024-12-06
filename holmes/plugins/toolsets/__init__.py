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
from holmes.utils.pydantic_utils import load_model_from_file

THIS_DIR = os.path.abspath(os.path.dirname(__file__))

class ListOfToolSets(BaseModel):
    toolsets: List[YAMLToolset]

def load_toolsets_from_file(path: str) -> List[YAMLToolset]:
    data: ListOfToolSets = load_model_from_file(ListOfToolSets, file_path=path)
    for toolset in data.toolsets:
        toolset.check_prerequisites()
        toolset.set_path(path)
    return data.toolsets

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
