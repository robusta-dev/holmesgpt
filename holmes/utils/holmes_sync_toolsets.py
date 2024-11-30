import yaml
from holmes.core.supabase_dal import SupabaseDal
from holmes.plugins.toolsets import load_builtin_toolsets, get_matching_toolsets
from holmes.common.env_vars import (
    HOLMES_HOST,
    HOLMES_PORT,
    DEFAULT_TOOLSETS,
    HOLMES_POST_PROCESSING_PROMPT,
    CLUSTER_NAME
)
import os
from pydantic import ValidationError 
from holmes.core.tools import DefaultToolsetYamlConfig, ToolsetYamlConfig, ToolsetDBModel
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.tools import TOols
from holmes.config import CUSTOM_TOOLSET_LOCATION

def holmes_sync_toolsets_status(dal: SupabaseDal):
    default_toolsets = load_builtin_toolsets()
    default_toolsets_names = {toolset.name for toolset in default_toolsets}

    matching_toolsets = get_matching_toolsets(
    default_toolsets, DEFAULT_TOOLSETS.split(",")
    )
    matching_toolsets_names = {toolset.name for toolset in matching_toolsets}

    validated_toolsets_from_config = []
    
    if os.path.isfile(CUSTOM_TOOLSET_LOCATION):
        with open(CUSTOM_TOOLSET_LOCATION) as file:
            parsed_yaml = yaml.safe_load(file)
            toolsets = parsed_yaml.get("toolsets", {})
            for name, config in toolsets.items():
                try:
                    if name in default_toolsets_names:
                        validated_toolsets_from_config.append(DefaultToolsetYamlConfig(**config, name=name))
                    else:
                        validated_config = ToolsetYamlConfig(**config, name=name)
                    validated_toolsets_from_config.append(validated_config)
                except ValidationError as e:
                    print(f"Toolset '{name}' is invalid: {e}")
    
    overrides = {toolset.name: toolset for toolset in validated_toolsets_from_config}
    enabled_toolsets = []
    for toolset in matching_toolsets:
        if toolset.name in overrides:
            override_toolset = overrides[toolset.name]
            if override_toolset.enabled:
                enabled_toolsets.append(override_toolset)
        else:
            enabled_toolsets.append(toolset)

    for toolset in validated_toolsets_from_config:
        if toolset not in enabled_toolsets and toolset.enabled:
            enabled_toolsets.append(toolset)
    from datetime import datetime
    db_toolsets = []
    updated_at = datetime.now().isoformat()
    for toolset in matching_toolsets:
        instructions = render_default_installation_instructions_for_toolset(toolset)
        toolset.check_prerequisites()
        if not toolset.installation_instructions:
            toolset.installation_instructions = instructions
        db_toolsets.append(ToolsetDBModel(**toolset.dict(exclude_none=True), 
                                          toolset_name=toolset.name,
                                          cluster_id=CLUSTER_NAME, 
                                          account_id=dal.account_id,
                                          updated_at=updated_at,
                                          status=toolset.get_status(),
                                          error=toolset.get_error(),
                                          ).model_dump(exclude_none=True))
    dal.sync_toolsets(db_toolsets)
    dal.get_toolsets_for_holmes()


def render_default_installation_instructions_for_toolset(
        toolset
):
    default_installation_instructions = load_and_render_prompt("file://holmes/utils/installation_guide.jinja2", {"env_vars": [toolset.get_environment_variables()]})
    return default_installation_instructions
