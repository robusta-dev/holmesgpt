from datetime import datetime
from typing import Any

import yaml


from holmes.config import Config
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import Toolset, ToolsetDBModel
from holmes.plugins.prompts import load_and_render_prompt


def holmes_sync_toolsets_status(dal: SupabaseDal, config: Config) -> None:
    """
    Method for synchronizing toolsets with the database:
    1) Fetch all built-in toolsets from the holmes/plugins/toolsets directory
    2) Load custom toolsets defined in /etc/holmes/config/custom_toolset.yaml
    3) Override default toolsets with corresponding custom configurations
       and add any new custom toolsets that are not part of the defaults
    4) Run the check_prerequisites method for each toolset
    5) Use sync_toolsets to upsert toolset's status and remove toolsets that are not loaded from configs or folder with default directory
    """
    tool_executor = config.create_tool_executor(dal)

    if not config.cluster_name:
        raise Exception(
            "Cluster name is missing in the configuration. Please ensure 'CLUSTER_NAME' is defined in the environment variables, "
            "or verify that a cluster name is provided in the Robusta configuration file."
        )

    db_toolsets = []
    updated_at = datetime.now().isoformat()
    for toolset in tool_executor.toolsets:
        if not toolset.installation_instructions:
            instructions = render_default_installation_instructions_for_toolset(toolset)
            toolset.installation_instructions = instructions
        db_toolsets.append(
            ToolsetDBModel(
                **toolset.model_dump(exclude_none=True),
                toolset_name=toolset.name,
                cluster_id=config.cluster_name,
                account_id=dal.account_id,
                status=toolset.get_status(),
                error=toolset.get_error(),
                updated_at=updated_at,
            ).model_dump(exclude_none=True)
        )
    dal.sync_toolsets(db_toolsets, config.cluster_name)


def render_default_installation_instructions_for_toolset(toolset: Toolset) -> str:
    env_vars = toolset.get_environment_variables()
    context: dict[str, Any] = {
        "env_vars": env_vars if env_vars else [],
        "toolset_name": toolset.name,
        "enabled": toolset.enabled,
        "example_config": yaml.dump(toolset.get_example_config()),
    }

    template = (
        "file://holmes/utils/default_toolset_installation_guide.jinja2"
        if toolset.is_default
        else "file://holmes/utils/installation_guide.jinja2"
    )
    installation_instructions = load_and_render_prompt(template, context)
    return installation_instructions
