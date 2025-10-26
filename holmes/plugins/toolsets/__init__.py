import logging
import os
import os.path
from typing import List, Optional

from holmes.plugins.toolsets.loaders import load_toolsets_from_file
from holmes.common.env_vars import (
    USE_LEGACY_KUBERNETES_LOGS,
    DISABLE_PROMETHEUS_TOOLSET,
)
from holmes.core.supabase_dal import SupabaseDal
from holmes.core.tools import (
    Toolset,
    ToolsetType,
)
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
from holmes.plugins.toolsets.grafana.loki.toolset_grafana_loki import GrafanaLokiToolset
from holmes.plugins.toolsets.grafana.toolset_grafana_tempo import GrafanaTempoToolset
from holmes.plugins.toolsets.internet.internet import InternetToolset
from holmes.plugins.toolsets.internet.notion import NotionToolset
from holmes.plugins.toolsets.kafka import KafkaToolset
from holmes.plugins.toolsets.kubernetes_logs import KubernetesLogsToolset
from holmes.plugins.toolsets.newrelic.newrelic import NewRelicToolset
from holmes.plugins.toolsets.opensearch.opensearch import OpenSearchToolset
from holmes.plugins.toolsets.opensearch.opensearch_logs import OpenSearchLogsToolset
from holmes.plugins.toolsets.opensearch.opensearch_query_assist import (
    OpenSearchQueryAssistToolset,
)
from holmes.plugins.toolsets.opensearch.opensearch_traces import OpenSearchTracesToolset
from holmes.plugins.toolsets.rabbitmq.toolset_rabbitmq import RabbitMQToolset
from holmes.plugins.toolsets.robusta.robusta import RobustaToolset
from holmes.plugins.toolsets.runbook.runbook_fetcher import RunbookToolset
from holmes.plugins.toolsets.servicenow_tables.servicenow_tables import (
    ServiceNowTablesToolset,
)
from holmes.plugins.toolsets.investigator.core_investigation import (
    CoreInvestigationToolset,
)

THIS_DIR = os.path.abspath(os.path.dirname(__file__))


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
        OpenSearchQueryAssistToolset(),
        CoralogixLogsToolset(),
        RabbitMQToolset(),
        GitToolset(),
        BashExecutorToolset(),
        MongoDBAtlasToolset(),
        RunbookToolset(dal=dal),
        AzureSQLToolset(),
        ServiceNowTablesToolset(),
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
