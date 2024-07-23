import logging
import os
import os.path
import subprocess
from typing import List

from pydantic import BaseModel

from holmes.core.tools import Toolset, ToolsetPrerequisite
from holmes.core.tools_langchain import LCToolset, LCToolsetPrerequisite
from holmes.utils.pydantic_utils import load_model_from_file

THIS_DIR = os.path.abspath(os.path.dirname(__file__))

class ListOfLCToolSets(BaseModel):
    toolsets: List[LCToolset]

class ListOfToolSets(BaseModel):
    toolsets: List[Toolset]

def load_toolsets_from_file(path: str) -> List[Toolset]:
    data: ListOfToolSets = load_model_from_file(ListOfToolSets, file_path=path)
    for toolset in data.toolsets:
        toolset.check_prerequisites()
        toolset.set_path(path)
    return data.toolsets


def load_lctoolsets_from_file(path: str) -> List[LCToolset]:
    data: ListOfLCToolSets = load_model_from_file(ListOfLCToolSets, file_path=path)
    for toolset in data.toolsets:
        toolset.check_prerequisites()
        toolset.set_path(path)
    return data.toolsets

def load_builtin_toolsets() -> List[Toolset]:
    all_toolsets = []
    logging.debug(f"loading toolsets from {THIS_DIR}")
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        all_toolsets.extend(load_toolsets_from_file(path))
    return all_toolsets


def load_builtin_lctoolsets() -> List[LCToolset]:
    all_toolsets = []
    logging.debug(f"loading toolsets from {THIS_DIR}")
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        all_toolsets.extend(load_lctoolsets_from_file(path))
    return all_toolsets