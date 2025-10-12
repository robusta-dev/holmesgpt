import logging
import os
import os.path
from typing import Any, Dict, List, Optional, Union

import yaml  # type: ignore
from pydantic import AnyUrl, ValidationError

import holmes.utils.env as env_utils
from holmes.common.env_vars import (
    USE_LEGACY_KUBERNETES_LOGS,
    DISABLE_PROMETHEUS_TOOLSET,
)
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import Toolset, ToolsetMetadata, ToolsetType, YAMLToolset

from holmes.plugins.toolsets.atlas_mongodb.mongodb_atlas import MongoDBAtlasToolset
from holmes.plugins.toolsets.azure_sql.azure_sql_toolset import AzureSQLToolset
from holmes.plugins.toolsets.bash.bash_toolset import BashExecutorToolset
from holmes.plugins.toolsets.coralogix.toolset_coralogix_logs import (
    CoralogixLogsToolset,
)
from holmes.plugins.toolsets.datadog.toolset_datadog_logs import DatadogLogsToolset
from holmes.plugins.toolsets.datadog.toolset_datadog_metrics import (
    DatadogMetricsToolset,
)
from holmes.plugins.toolsets.datadog.toolset_datadog_traces import (
    DatadogTracesToolset,
)
from holmes.plugins.toolsets.datadog.toolset_datadog_rds import (
    DatadogRDSToolset,
)
from holmes.plugins.toolsets.datadog.toolset_datadog_general import (
    DatadogGeneralToolset,
)
from holmes.plugins.toolsets.git import GitToolset
from holmes.plugins.toolsets.grafana.toolset_grafana import GrafanaToolset
from holmes.plugins.toolsets.grafana.toolset_grafana_loki import GrafanaLokiToolset
from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import GrafanaTempoToolset
from holmes.plugins.toolsets.internet.internet import InternetToolset
from holmes.plugins.toolsets.internet.notion import NotionToolset
from holmes.plugins.toolsets.kafka import KafkaToolset
from holmes.plugins.toolsets.kubernetes_logs import KubernetesLogsToolset
from holmes.plugins.toolsets.mcp.toolset_mcp import RemoteMCPToolset
from holmes.plugins.toolsets.newrelic.newrelic import NewRelicToolset
from holmes.plugins.toolsets.opensearch.opensearch import OpenSearchToolset
from holmes.plugins.toolsets.opensearch.opensearch_logs import OpenSearchLogsToolset
from holmes.plugins.toolsets.opensearch.opensearch_traces import OpenSearchTracesToolset
from holmes.plugins.toolsets.rabbitmq.toolset_rabbitmq import RabbitMQToolset
from holmes.plugins.toolsets.robusta.robusta import RobustaToolset
from holmes.plugins.toolsets.runbook.runbook_fetcher import RunbookToolset
from holmes.plugins.toolsets.servicenow.servicenow import ServiceNowToolset
from holmes.plugins.toolsets.investigator.core_investigation import (
    CoreInvestigationToolset,
)

THIS_DIR = os.path.abspath(os.path.dirname(__file__))


class MCPServerConfig(ToolsetMetadata):
    """Configuration for MCP servers from config files"""

    url: AnyUrl

    # Override default for MCP servers
    enabled: bool = True


def load_toolsets_from_file(toolsets_path: str) -> List[Toolset]:
    toolsets = []
    with open(toolsets_path) as file:
        parsed_yaml = yaml.safe_load(file)
        if parsed_yaml is None:
            raise ValueError(
                f"Failed to load toolsets from {toolsets_path}: file is empty or invalid YAML."
            )
        toolsets_dict = parsed_yaml.get("toolsets", {})

        # Note: strict_check parameter is no longer used, kept for backwards compatibility
        toolsets.extend(load_toolsets_from_config(toolsets_dict))

    return toolsets


def load_python_toolsets(dal: Optional[SupabaseDal]) -> List[Toolset]:
    logging.debug("loading python toolsets")

    toolsets: list[Toolset] = [
        CoreInvestigationToolset(),  # Load first for higher priority
        InternetToolset(),
        RobustaToolset(dal),
        OpenSearchToolset(),
        GrafanaLokiToolset(),
        GrafanaTempoToolset(),
        NewRelicToolset(),
        GrafanaToolset(),
        NotionToolset(),
        KafkaToolset(),
        DatadogLogsToolset(),
        DatadogGeneralToolset(),
        DatadogMetricsToolset(),
        DatadogTracesToolset(),
        DatadogRDSToolset(),
        OpenSearchLogsToolset(),
        OpenSearchTracesToolset(),
        CoralogixLogsToolset(),
        RabbitMQToolset(),
        GitToolset(),
        BashExecutorToolset(),
        MongoDBAtlasToolset(),
        RunbookToolset(),
        AzureSQLToolset(),
        ServiceNowToolset(),
    ]

    if not DISABLE_PROMETHEUS_TOOLSET:
        from holmes.plugins.toolsets.prometheus.prometheus import PrometheusToolset

        toolsets.append(PrometheusToolset())

    if not USE_LEGACY_KUBERNETES_LOGS:
        toolsets.append(KubernetesLogsToolset())

    return toolsets


def load_builtin_toolsets(dal: Optional[SupabaseDal] = None) -> List[Toolset]:
    all_toolsets: List[Toolset] = []
    logging.debug(f"loading toolsets from {THIS_DIR}")

    # Handle YAML toolsets
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue

        if filename == "kubernetes_logs.yaml" and not USE_LEGACY_KUBERNETES_LOGS:
            continue

        path = os.path.join(THIS_DIR, filename)
        toolsets_from_file = load_toolsets_from_file(path)
        all_toolsets.extend(toolsets_from_file)

    all_toolsets.extend(load_python_toolsets(dal=dal))  # type: ignore

    # disable built-in toolsets by default, and the user can enable them explicitly in config.
    for toolset in all_toolsets:
        toolset.type = ToolsetType.BUILTIN
        # dont' expose build-in toolsets path
        toolset.path = None

    return all_toolsets  # type: ignore


def load_mcp_servers(servers_config: Dict[str, Dict[str, Any]]) -> List[Toolset]:
    """
    Load MCP servers with proper URL handling at top level.

    :param servers_config: Dictionary of MCP server configurations
    :return: List of RemoteMCPToolset objects
    """
    if not servers_config:
        return []

    loaded_servers: List[Toolset] = []

    for name, config in servers_config.items():
        try:
            # Apply environment variable substitution to entire config first
            config = env_utils.replace_env_vars_values(config)

            # Add name to config dict for parsing
            config["name"] = name

            # Parse and validate MCP server config
            mcp_config = MCPServerConfig(**config)

            # Create RemoteMCPToolset with url at top level
            toolset = RemoteMCPToolset(
                name=name,
                url=mcp_config.url,  # type: ignore[arg-type]  # Pydantic handles str -> AnyUrl conversion
                description=mcp_config.description,
                enabled=mcp_config.enabled,
                config=mcp_config.config,
                icon_url=mcp_config.icon_url
                or "https://registry.npmmirror.com/@lobehub/icons-static-png/1.46.0/files/light/mcp.png",
                docs_url=mcp_config.docs_url,
                installation_instructions=mcp_config.installation_instructions,
                additional_instructions=mcp_config.additional_instructions,
            )

            # Mark as MCP type
            toolset.type = ToolsetType.MCP

            loaded_servers.append(toolset)

        except ValidationError as e:
            logging.error(f"Invalid MCP server '{name}': {e}")
            # Continue loading other servers
        except Exception as e:
            logging.error(f"Failed to load MCP server '{name}': {e}", exc_info=True)
            # Continue loading other servers

    return loaded_servers


def is_old_toolset_config(
    toolsets: Union[dict[str, dict[str, Any]], List[dict[str, Any]]],
) -> bool:
    # old config is a list of toolsets
    if isinstance(toolsets, list):
        return True
    return False


def load_toolsets_from_config(
    toolsets: dict[str, dict[str, Any]],
) -> List[Toolset]:
    """
    Load NEW custom toolsets from a dictionary configuration.
    Only used for creating new toolsets, not for configuring existing ones.
    :param toolsets: Dictionary of toolset configurations.
    :return: List of validated Toolset objects.
    """

    if not toolsets:
        return []

    loaded_toolsets: list[Toolset] = []
    if is_old_toolset_config(toolsets):
        message = "Old toolset config format detected, please update to the new format: https://holmesgpt.dev/data-sources/custom-toolsets/"
        logging.warning(message)
        raise ValueError(message)

    for name, config in toolsets.items():
        try:
            # Note: MCP servers should now be loaded via load_mcp_servers()
            # This function only handles YAML toolsets
            validated_toolset = YAMLToolset(**config, name=name)  # type: ignore

            if validated_toolset.config:
                validated_toolset.config = env_utils.replace_env_vars_values(
                    validated_toolset.config
                )
            loaded_toolsets.append(validated_toolset)
        except ValidationError as e:
            logging.error(f"Toolset '{name}' is invalid: {e}")
            # Continue loading other toolsets instead of failing completely

        except Exception as e:
            logging.error(f"Failed to load toolset '{name}': {e}", exc_info=True)
            # Continue loading other toolsets instead of failing completely

    return loaded_toolsets
