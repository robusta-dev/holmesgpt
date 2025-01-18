import yaml
from holmes.core.supabase_dal import SupabaseDal
from holmes.plugins.toolsets import load_builtin_toolsets
from holmes.core.tools import get_matching_toolsets
import os
from pydantic import ValidationError
from holmes.core.tools import ToolsetYamlFromConfig, ToolsetDBModel, YAMLToolset, ToolsetTag, ToolsetStatusEnum
from holmes.plugins.prompts import load_and_render_prompt
from holmes.utils.definitions import CUSTOM_TOOLSET_LOCATION
import logging
from datetime import datetime 


def load_custom_toolsets_config() -> list[ToolsetYamlFromConfig]:
    """
    Loads toolsets config from /etc/holmes/config/custom_toolset.yaml with ToolsetYamlFromConfig class
    that doesn't have strict validations. 
    Example configuration:

    kubernetes/logs:
        enabled: false
  
    test/configurations:
        enabled: true
        icon_url: "example.com"
        description: "test_description"
        docs_url: "https://docs.docker.com/"
        prerequisites:
            - env:
                - API_ENDPOINT
            - command: "curl ${API_ENDPOINT}"
        additional_instructions: "jq -r '.result.results[].userData | fromjson | .text | fromjson | .log'"
        tools:
            - name: "curl_example"
            description: "Perform a curl request to example.com using variables"
            command: "curl -X GET '{{api_endpoint}}?query={{ query_param }}' "
    """
    loaded_toolsets = []
    if os.path.isfile(CUSTOM_TOOLSET_LOCATION):
        with open(CUSTOM_TOOLSET_LOCATION) as file:
            parsed_yaml = yaml.safe_load(file)
            toolsets = parsed_yaml.get("toolsets", {})
            for name, config in toolsets.items():
                try:
                    validated_config = ToolsetYamlFromConfig(**config, name=name)
                    validated_config.set_path(CUSTOM_TOOLSET_LOCATION)
                    loaded_toolsets.append(validated_config)
                except ValidationError as e:
                    logging.error(f"Toolset '{name}' is invalid: {e}")
    return loaded_toolsets


def merge_and_override_bultin_toolsets_with_toolsets_config(
    toolsets_loaded_from_config: list[ToolsetYamlFromConfig],
    default_toolsets_by_name: dict[str, YAMLToolset],
) -> dict[str, YAMLToolset]:
    """
    Merges and overrides default_toolsets_by_name with custom 
    config from /etc/holmes/config/custom_toolset.yaml
    """
    toolsets_with_updated_statuses = {
        toolset.name: toolset for toolset in default_toolsets_by_name.values()
    }
    
    for toolset in toolsets_loaded_from_config:
        if toolset.name in toolsets_with_updated_statuses.keys():
            toolsets_with_updated_statuses[toolset.name].override_with(toolset)
        else:
            try:
                validated_toolset = YAMLToolset(**toolset.model_dump(exclude_none=True))
                toolsets_with_updated_statuses[toolset.name] = validated_toolset
            except Exception as error:
                logging.error(
                    f"Toolset '{toolset.name}' is invalid: {error} ", exc_info=True
                )
    
    return toolsets_with_updated_statuses


def holmes_sync_toolsets_status(dal: SupabaseDal, config) -> None:
    """
    Method for synchronizing toolsets with the database:
    1) Fetch all built-in toolsets from the holmes/plugins/toolsets directory
    2) Load custom toolsets defined in /etc/holmes/config/custom_toolset.yaml
    3) Override default toolsets with corresponding custom configurations
       and add any new custom toolsets that are not part of the defaults
    4) Run the check_prerequisites method for each toolset
    5) Use sync_toolsets to upsert toolset's status and remove toolsets that are not loaded from configs or folder with default directory
    """
    default_toolsets = [toolset for toolset in load_builtin_toolsets(dal) if any(tag in (ToolsetTag.CORE, ToolsetTag.CLUSTER) for tag in toolset.tags)]
    default_toolsets_by_name = {toolset.name: toolset for toolset in default_toolsets}

    toolsets_loaded_from_config = load_custom_toolsets_config()

    toolsets_for_sync_by_name = merge_and_override_bultin_toolsets_with_toolsets_config(
        toolsets_loaded_from_config, default_toolsets_by_name
    )

    # we check every toolset and save to local config toolsets which have passed the checks
    # before we try to upsert anything to db
    for toolset in toolsets_for_sync_by_name.values():
        if toolset.enabled:
            toolset.check_prerequisites()
    
    config.enabled_toolsets_names = []

    if not config.cluster_name:
        raise Exception("Cluster name is missing in the configuration. Please ensure 'CLUSTER_NAME' is defined in the environment variables, "
        "or verify that a cluster name is provided in the Robusta configuration file.")
    
    db_toolsets = []
    updated_at = datetime.now().isoformat()
    for toolset in toolsets_for_sync_by_name.values():
        if not toolset.installation_instructions:
            is_default_toolset = bool(toolset.name in default_toolsets_by_name.keys())
            instructions = render_default_installation_instructions_for_toolset(
                toolset, is_default_toolset
            )
            toolset.installation_instructions = instructions
        db_toolsets.append(
            ToolsetDBModel(
                **toolset.model_dump(exclude_none=True),
                toolset_name=toolset.name,
                cluster_id=config.cluster_name,
                account_id=dal.account_id,
                status=toolset.get_status(),
                error=toolset.get_error(),
                updated_at=updated_at
            ).model_dump(exclude_none=True)
        )
    dal.sync_toolsets(db_toolsets, config.cluster_name)


def render_default_installation_instructions_for_toolset(
    toolset: YAMLToolset, default_toolset: bool
):
    env_vars = toolset.get_environment_variables()
    context = {
        "env_vars": env_vars if env_vars else [],
        "toolset_name": toolset.name,
        "enabled": toolset.enabled,
        "default_toolset": default_toolset
    }
    if default_toolset:
        installation_instructions = load_and_render_prompt(
            "file://holmes/utils/default_toolset_installation_guide.jinja2", context
        )
        return installation_instructions
    installation_instructions = load_and_render_prompt(
        "file://holmes/utils/installation_guide.jinja2", context
    )
    return installation_instructions
