# Built-in Toolsets

Holmes allows defining integrations (toolsets) that fetch data from external sources. Some toolsets are enabled by default, while others require the user to add their own configuration/credentials.

## Available Toolsets

<div class="grid cards" markdown>

-   [:simple-argo:{ .lg .middle } **ArgoCD**](argocd.md)
-   [:material-aws:{ .lg .middle } **AWS**](aws.md)
-   [:simple-confluence:{ .lg .middle } **Confluence**](confluence.md)
-   [:material-chart-line:{ .lg .middle } **Coralogix logs**](coralogix-logs.md)
-   [:simple-datadog:{ .lg .middle } **DataDog**](datadog.md)
-   [:material-clock:{ .lg .middle } **Datetime**](datetime.md)
-   [:simple-docker:{ .lg .middle } **Docker**](docker.md)
-   [:material-github:{ .lg .middle } **GitHub**](github.md)
-   [:simple-grafana:{ .lg .middle } **Grafana Loki**](grafanaloki.md)
-   [:simple-grafana:{ .lg .middle } **Grafana Tempo**](grafanatempo.md)
-   [:material-package:{ .lg .middle } **Helm**](helm.md)
-   [:material-web:{ .lg .middle } **Internet**](internet.md)
-   [:simple-apachekafka:{ .lg .middle } **Kafka**](kafka.md)
-   [:simple-kubernetes:{ .lg .middle } **Kubernetes**](kubernetes.md)
-   [:simple-notion:{ .lg .middle } **Notion**](notion.md)
-   [:simple-newrelic:{ .lg .middle } **New Relic**](newrelic.md)
-   [:simple-opensearch:{ .lg .middle } **OpenSearch logs**](opensearch-logs.md)
-   [:simple-opensearch:{ .lg .middle } **OpenSearch status**](opensearch-status.md)
-   [:simple-prometheus:{ .lg .middle } **Prometheus**](prometheus.md)
-   [:simple-rabbitmq:{ .lg .middle } **RabbitMQ**](rabbitmq.md)
-   [:material-robot:{ .lg .middle } **Robusta**](robusta.md)
-   [:material-forum:{ .lg .middle } **Slab**](slab.md)
-   [:material-ticket:{ .lg .middle } **ServiceNow**](servicenow.md)
-   [:material-microsoft-azure:{ .lg .middle } **Azure Kubernetes Service**](aks.md)
-   [:material-heart-pulse:{ .lg .middle } **AKS Node Health**](aks-node-health.md)
-   [:material-api:{ .lg .middle } **Model Context Protocol**](mcp.md)

</div>

## Getting Started

1. **Review** the toolsets relevant to your infrastructure
2. **Configure** authentication for external services
3. **Test** investigations to see which data sources are accessed

Some toolsets work automatically with Kubernetes, while external services require API keys or credentials to be configured.
