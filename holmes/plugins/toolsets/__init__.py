import logging
import os
import os.path
from typing import List, Optional

import yaml  # type: ignore

from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import Toolset, YAMLToolset
from holmes.plugins.toolsets.bash.bash_toolset import BashExecutorToolset
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
from holmes.plugins.toolsets.log_filter import LogFilterToolset
from holmes.plugins.toolsets.newrelic import NewRelicToolset
from holmes.plugins.toolsets.opensearch.opensearch import OpenSearchToolset
from holmes.plugins.toolsets.opensearch.opensearch_logs import OpenSearchLogsToolset
from holmes.plugins.toolsets.opensearch.opensearch_traces import OpenSearchTracesToolset
from holmes.plugins.toolsets.prometheus.prometheus import PrometheusToolset
from holmes.plugins.toolsets.rabbitmq.toolset_rabbitmq import RabbitMQToolset
from holmes.plugins.toolsets.robusta.robusta import RobustaToolset

THIS_DIR = os.path.abspath(os.path.dirname(__file__))


def load_toolsets_from_file(
    path: str, silent_fail: bool = False, is_default: bool = False
) -> List[YAMLToolset]:
    file_toolsets = []
    with open(path) as file:
        parsed_yaml = yaml.safe_load(file)
        toolsets = parsed_yaml.get("toolsets", {})
        for name, config in toolsets.items():
            try:
                toolset = YAMLToolset(**config, name=name, is_default=is_default)
                toolset.set_path(path)
                file_toolsets.append(YAMLToolset(**config, name=name))
            except Exception:
                if not silent_fail:
                    logging.error(
                        f"Error happened while loading {name} toolset from {path}",
                        exc_info=True,
                    )

    return file_toolsets


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
        BashExecutorToolset(),
        LogFilterToolset(),
    ]

    return toolsets


def load_builtin_toolsets(dal: Optional[SupabaseDal] = None) -> List[Toolset]:
    all_toolsets = []
    logging.debug(f"loading toolsets from {THIS_DIR}")

    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        toolsets_from_file = load_toolsets_from_file(path, is_default=True)
        all_toolsets.extend(toolsets_from_file)

    all_toolsets.extend(load_python_toolsets(dal=dal))  # type: ignore
    return all_toolsets  # type: ignore
