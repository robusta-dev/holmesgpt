from holmes.core.tools import ToolParameter, ToolsetTag
from typing import Dict, Any
from holmes.core.tools import Tool, Toolset
from holmes.core.tools import StructuredToolResult, ToolResultStatus
# Disabled & failed Toolsets

all = """
If you need a toolset to access a system that you don't otherwise have access to:
  - Make sure a toolset's description matches what is needed before recommending it
  - Ask the user to configure the toolset. Ensure you provide a toolset name from the list below.
  - Call fetch_webpage on the toolset URL and repeat to the user how to setup the toolset
  - Share the URL with the user in addition to repeating the setup steps
  - If the toolset is in "failed" status. Tell the user and copy the error in your response for the user to see
  - If there are no relevant toolsets in the list below, tell the user that you are missing an integration to access XYZ:
    you should give an answer similar to "I don't have access to <system>. Please add a Holmes integration for <system> so
    that I can investigate this."

The following toolsets are either disabled or failed to initialize:


* toolset name: kubernetes/live-metrics
    *  status: disabled
    *  description: Provides real-time metrics for pods and nodes
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/kubernetes.html#live-metrics
* toolset name: kubernetes/kube-lineage-extras
    *  status: disabled
    *  description: Fetches children/dependents and parents/dependencies resources using kube-lineage
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/kubernetes.html#resource-lineage-extras
* toolset name: helm/core
    *  status: disabled
    *  description: Read access to cluster's Helm charts and releases
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/helm.html
* toolset name: argocd/core
    *  status: disabled
    *  description: Set of tools to get argocd metadata like list of apps, repositories, projects, etc.
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/argocd.html
* toolset name: confluence
    *  status: disabled
    *  description: Fetch confluence pages
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/confluence.html
* toolset name: aws/rds
    *  status: disabled
    *  description: Read access to Amazon RDS resources
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/aws.html#rds
* toolset name: slab
    *  status: disabled
    *  description: Fetches slab pages
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/slab.html
* toolset name: servicenow
    *  status: disabled
    *  description: Fetch change requests from ServiceNow
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/servicenow.html
* toolset name: opensearch/status
    *  status: disabled
    *  description: Provide cluster metadata information like health, shards, settings.
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/opensearch.html
* toolset name: grafana/loki
    *  status: disabled
    *  description: Fetches kubernetes pods and node logs from Loki
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafanaloki.html
* toolset name: grafana/tempo
    *  status: disabled
    *  description: Fetches kubernetes traces from Tempo
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafanatempo.html
* toolset name: grafana/grafana
    *  status: disabled
    *  description: Provides tools for interacting with Grafana dashboards
* toolset name: notion
    *  status: disabled
    *  description: Fetch notion webpages
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/notion.html
* toolset name: kafka/admin
    *  status: disabled
    *  description: Fetches metadata from multiple Kafka clusters
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/kafka.html
* toolset name: opensearch/logs
    *  status: disabled
    *  description: OpenSearch integration to fetch logs
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/opensearch-logs.html
* toolset name: opensearch/traces
    *  status: disabled
    *  description: OpenSearch integration to fetch traces
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/opensearch-traces.html
* toolset name: coralogix/logs
    *  status: failed, reason: Failed with status_code=403.
    *  description: Toolset for interacting with Coralogix to fetch logs
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/coralogix_logs.html
* toolset name: rabbitmq/core
    *  status: failed, reason: Toolset failed health check for cluster with id=rabbitmq at http://rabbitmq.rabbitmq:15672/api/overview due to a failed http request. Connection error: 401 Client Error: Unauthorized for url: http://rabbitmq.rabbitmq:15672/api/overview
    *  description: Provides tools to interact with RabbitMQ Management API for diagnosing cluster health, node status, and specifically network partitions (split-brain).
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/rabbitmq.html
"""

rabbitmq = """
If you tools to access rabbitmq and you don't otherwise have access to it:
  - If the toolset `rabbitmq/core` has status=disabled. Ask the user to configure the toolset. Ensure you provide a toolset name from the list below.
  - Call fetch_webpage on the toolset URL and repeat to the user how to setup the toolset
  - Share the URL with the user in addition to repeating the setup steps
  - If the toolset is in "failed" status. Tell the user and copy the error in your response for the user to see
  - If there are no relevant toolsets in the list below, tell the user that you are missing an integration to access XYZ:
    you should give an answer similar to "I don't have access to <system>. Please add a Holmes integration for <system> so
    that I can investigate this."

* toolset name: rabbitmq/core
    *  status: failed, reason: Toolset failed health check for cluster with id=rabbitmq at http://rabbitmq.rabbitmq:15672/api/overview due to a failed http request. Connection error: 401 Client Error: Unauthorized for url: http://rabbitmq.rabbitmq:15672/api/overview
    *  description: Provides tools to interact with RabbitMQ Management API for diagnosing cluster health, node status, and specifically network partitions (split-brain).
    *  setup instructions: https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/rabbitmq.html
"""


class FetchIntegrationInfo(Tool):
    def __init__(self):
        super().__init__(
            name="fetch_integration_info",
            description="Fetch information about an integration",
            parameters={
                "name": ToolParameter(
                    description="The name of the integration. Optional. If empty, all current integrations will be returned",
                    type="string",
                    required=False,
                ),
            },
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data=rabbitmq.strip(),
            params=params,
        )

    def get_parameterized_one_liner(self, params) -> str:
        return "fetched current time"


class IntegrationToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="toolsets",
            enabled=True,
            description="Fetch status and information about current toolsets",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/datetime.html",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/8/8b/OOjs_UI_icon_calendar-ltr.svg",
            prerequisites=[],
            tools=[FetchIntegrationInfo()],
            tags=[ToolsetTag.CORE],
            is_default=True,
        )

    def get_example_config(self) -> Dict[str, Any]:
        return {}
