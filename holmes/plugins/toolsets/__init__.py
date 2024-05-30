import logging
import os
import os.path
import subprocess
from typing import List

from pydantic import BaseModel

from holmes.core.tools import Toolset, ToolsetPrerequisite
from holmes.utils.pydantic_utils import load_model_from_file

THIS_DIR = os.path.dirname(__file__)

class ListOfToolSets(BaseModel):
    toolsets: List[Toolset]

def load_toolsets_from_file(path: str) -> List[Toolset]:
    data: ListOfToolSets = load_model_from_file(ListOfToolSets, file_path=path)
    for toolset in data.toolsets:
        toolset.check_prerequisites()
        toolset.set_path(path)
    return data.toolsets

def load_builtin_toolsets() -> List[Toolset]:
    all_toolsets = []
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        all_toolsets.extend(load_toolsets_from_file(path))
    return all_toolsets
