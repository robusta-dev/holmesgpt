import logging
import os
import os.path
from typing import List, Optional

from holmes.core.supabase_dal import SupabaseDal
from holmes.plugins.toolsets.findings import FindingsToolset
from holmes.plugins.toolsets.internet import InternetToolset
from pydantic import BaseModel

from holmes.core.tools import Toolset, YAMLToolset, ToolsetYamlConfig, ToolsetDBModel, get_matching_toolsets, DefaultToolsetYamlConfig
from holmes.utils.pydantic_utils import load_model_from_file
#from holmes.config import CUSTOM_TOOLSET_LOCATION
from typing import Dict
from pydantic import BaseModel, ValidationError, Field
from typing import Optional
import yaml
from holmes.common.env_vars import (
    HOLMES_HOST,
    HOLMES_PORT,
    DEFAULT_TOOLSETS,
    HOLMES_POST_PROCESSING_PROMPT,
)
from holmes.config import CUSTOM_TOOLSET_LOCATION

THIS_DIR = os.path.abspath(os.path.dirname(__file__))


class FallbackOldStructureToolsetsList(BaseModel):
    toolsets: List[YAMLToolset]


class ToolsetsYaml(BaseModel):
    toolsets: Dict[str, YAMLToolset]


def load_toolsets_from_file(path: str) -> List[YAMLToolset]:
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
                logging.error("",exc_info=True)

    return file_toolsets


def load_python_toolsets(dal:Optional[SupabaseDal]) -> List[Toolset]:
    logging.debug("loading python toolsets")
    return [InternetToolset(), FindingsToolset(dal)]


def load_builtin_toolsets(dal:Optional[SupabaseDal] = None) -> List[Toolset]:
    all_toolsets = []
    logging.debug(f"loading toolsets from {THIS_DIR}")
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        all_toolsets.extend(load_toolsets_from_file(path))

    all_toolsets.extend(load_python_toolsets(dal))
    return all_toolsets



def load_toolsets_config(dal:SupabaseDal):
    validated_toolsets_from_config = []
    default_toolsets = load_builtin_toolsets()
    #print(default_toolsets)
    if DEFAULT_TOOLSETS == "*":
        matching_toolsets = default_toolsets
    else:
        matching_toolsets = get_matching_toolsets(
            default_toolsets, DEFAULT_TOOLSETS.split(",")
            )
    #print(matching_toolsets)
    matching_toolsets_names = [toolset.name for toolset in matching_toolsets]
    print(matching_toolsets_names)

    if os.path.isfile(CUSTOM_TOOLSET_LOCATION):
        with open(CUSTOM_TOOLSET_LOCATION) as file:
            parsed_yaml = yaml.safe_load(file)
            toolsets = parsed_yaml.get("toolsets", {})
            for name, config in toolsets.items():
                try:
                    print("NAME", name)
                # Validate the config for the current toolset
                    if name in matching_toolsets_names:
                        print("NAME IN TOOLSETS")
                        validated_toolsets_from_config.append(DefaultToolsetYamlConfig(**config, name=name))
                        print("appended?")
                    else:
                        validated_config = ToolsetYamlConfig(**config, name=name)
                    #print(f"Toolset '{name}' is valid: {validated_config}")
                    validated_toolsets_from_config.append(validated_config)
                except ValidationError as e:
                    print(f"Toolset '{name}' is invalid: {e}")

    
    print([toolset.name for toolset in matching_toolsets])
    enabled_toolsets_from_config_names = [toolset.name for toolset in validated_toolsets_from_config]
    print("enabled toolsets", enabled_toolsets_from_config_names)
    for toolset in matching_toolsets:
        print(toolset.name)
        print(enabled_toolsets_from_config_names)
        if toolset.name in enabled_toolsets_from_config_names:
            enabled = toolsets.get(toolset.name)["enabled"]
            print(enabled)
            if not enabled:
                print("not enabled")
                matching_toolsets.remove(toolset)
    matching_toolsets_names = [toolset.name for toolset in matching_toolsets]
    enabled_toolsets_from_config_names = [toolset.name for toolset in validated_toolsets_from_config if toolset.enabled is True]
    #intersection = list(set(matching_toolsets).intersection(set(enabled_toolsets_from_config)))
    #print(intersection)
    #print([toolset.name for toolset in intersection])
    print(matching_toolsets_names)
    print(enabled_toolsets_from_config_names)
    db_toolsets = []
    for toolset in matching_toolsets:
        toolset.check_prerequisites()
        db_toolsets.append(ToolsetDBModel(**toolset.dict(), toolset_name=toolset.name))
    #dal.sync_toolsets(db_toolsets)
        #try:
        #    toolsets = load_model_from_file(ToolsetsYaml, file_path="/home/itisallgood/Documents/robustagpt/holmesgpt/.vscode/testtoolset.yaml")
        #except Exception as error:
        #    logging.error(f"An error happened while trying to use custom toolset: {error}", exc_info=True)
    #print(toolsets)