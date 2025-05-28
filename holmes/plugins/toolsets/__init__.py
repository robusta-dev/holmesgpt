import logging
import os
import os.path
from typing import Any, List, Optional, Union

import yaml  # type: ignore
from pydantic import FilePath, ValidationError

import holmes.utils.env as env_utils
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import Toolset, ToolsetType, ToolsetYamlFromConfig, YAMLToolset
from holmes.plugins.toolsets.coralogix.toolset_coralogix_logs import (
    CoralogixLogsToolset,
)
from holmes.plugins.toolsets.datadog import DatadogToolset
from holmes.plugins.toolsets.datetime import DatetimeToolset
from holmes.plugins.toolsets.git import GitToolset
from holmes.plugins.toolsets.grafana.toolset_grafana import GrafanaToolset
from holmes.plugins.toolsets.grafana.toolset_grafana_loki import GrafanaLokiToolset
from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import GrafanaTempoToolset
from holmes.plugins.toolsets.internet.internet import InternetToolset
from holmes.plugins.toolsets.internet.notion import NotionToolset
from holmes.plugins.toolsets.kafka import KafkaToolset
from holmes.plugins.toolsets.mcp.toolset_mcp import RemoteMCPToolset
from holmes.plugins.toolsets.newrelic import NewRelicToolset
from holmes.plugins.toolsets.opensearch.opensearch import OpenSearchToolset
from holmes.plugins.toolsets.opensearch.opensearch_logs import OpenSearchLogsToolset
from holmes.plugins.toolsets.opensearch.opensearch_traces import OpenSearchTracesToolset
from holmes.plugins.toolsets.prometheus.prometheus import PrometheusToolset
from holmes.plugins.toolsets.rabbitmq.toolset_rabbitmq import RabbitMQToolset
from holmes.plugins.toolsets.robusta.robusta import RobustaToolset

THIS_DIR = os.path.abspath(os.path.dirname(__file__))


def load_toolsets_from_file(
    toolsets_path: str,
    is_default: bool = False,
    type: ToolsetType = ToolsetType.BUILTIN,
) -> List[YAMLToolset]:
    toolsets = []
    with open(toolsets_path) as file:
        parsed_yaml = yaml.safe_load(file)
        if parsed_yaml is None:
            raise ValueError(
                f"Failed to load toolsets from {toolsets_path}: file is empty or invalid YAML."
            )
        toolsets_dict = parsed_yaml.get("toolsets", {})

        toolsets.extend(load_toolsets_config(toolsets_dict, toolsets_path, type))

    for toolset in toolsets:
        toolset.is_default = is_default

    return toolsets


def load_python_toolsets(dal: Optional[SupabaseDal]) -> List[Toolset]:
    logging.debug("loading python toolsets")
    toolsets: list[Toolset] = [
        InternetToolset(),
        RobustaToolset(dal),
        OpenSearchToolset(),
        GrafanaLokiToolset(),
        GrafanaTempoToolset(),
        NewRelicToolset(),
        GrafanaToolset(),
        NotionToolset(),
        KafkaToolset(),
        DatadogToolset(),
        PrometheusToolset(),
        DatetimeToolset(),
        OpenSearchLogsToolset(),
        OpenSearchTracesToolset(),
        CoralogixLogsToolset(),
        RabbitMQToolset(),
        GitToolset(),
    ]

    return toolsets


def load_builtin_toolsets(dal: Optional[SupabaseDal] = None) -> List[Toolset]:
    all_toolsets = []
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        toolsets_from_file = load_toolsets_from_file(
            path, is_default=True, type=ToolsetType.BUILTIN
        )
        all_toolsets.extend(toolsets_from_file)

    all_toolsets.extend(load_python_toolsets(dal=dal))  # type: ignore
    return all_toolsets  # type: ignore


def is_old_toolset_config(
    toolsets: Union[dict[str, dict[str, Any]], List[dict[str, Any]]],
) -> bool:
    # old config is a list of toolsets
    if isinstance(toolsets, list):
        return True
    return False


def load_toolsets_config(
    toolsets: dict[str, dict[str, Any]],
    path: Optional[FilePath] = None,
    type: ToolsetType = ToolsetType.BUILTIN,
    strict_check: bool = True,
) -> List[YAMLToolset]:
    """
    Load toolsets from a dictionary or list of dictionaries.
    :param toolsets: Dictionary of toolsets or list of toolset configurations.
    :param path: Optional path to the toolset configuration file.
    :param type: Type of the toolset (e.g., BUILTIN, CUSTOM).
    :param strict_check: If True, all required fields for a toolset must be present.
    :return: List of validated YAMLToolset objects.
    """

    if not toolsets:
        return []

    loaded_toolsets: list[YAMLToolset] = []
    if is_old_toolset_config(toolsets):
        message = "Old toolset config format detected, please update to the new format: https://docs.robusta.dev/master/configuration/holmesgpt/custom_toolsets.html"
        logging.warning(message)
        raise ValueError(message)

    for name, config in toolsets.items():
        # ignore the built-in toolset path
        if type == ToolsetType.BUILTIN or type == ToolsetType.MCP:
            path = None
        try:
            if strict_check:
                if type == ToolsetType.MCP:
                    validated_toolset = RemoteMCPToolset(
                        **config, path=path, type=type, name=name
                    )
                else:
                    validated_toolset: YAMLToolset = YAMLToolset(  # type: ignore
                        **config, path=path, type=type, name=name
                    )
            else:
                validated_toolset: ToolsetYamlFromConfig = ToolsetYamlFromConfig(  # type: ignore
                    **config, path=path, type=type, name=name
                )

            if validated_toolset.config:
                validated_toolset.config = env_utils.replace_env_vars_values(
                    validated_toolset.config
                )
            loaded_toolsets.append(validated_toolset)
        except ValidationError as e:
            logging.warning(f"Toolset '{name}' is invalid: {e}")

        except Exception:
            logging.warning("Failed to load toolset: %s", name, exc_info=True)

    return loaded_toolsets
