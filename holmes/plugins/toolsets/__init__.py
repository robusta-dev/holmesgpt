import logging
import os
import os.path
import subprocess
from typing import List

from holmes.plugins.toolsets.findings import FindingsToolset
from holmes.plugins.toolsets.internet import InternetToolset
from pydantic import BaseModel

from holmes.core.tools import Toolset, YAMLToolset
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

def load_python_toolsets() -> List[Toolset]:
    logging.debug(f"loading python toolsets")
    return [InternetToolset(), FindingsToolset()]

def load_builtin_toolsets() -> List[Toolset]:
    all_toolsets = []
    logging.debug(f"loading toolsets from {THIS_DIR}")
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        all_toolsets.extend(load_toolsets_from_file(path))

    all_toolsets.extend(load_python_toolsets())
    return all_toolsets
