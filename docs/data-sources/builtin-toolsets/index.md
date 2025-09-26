# Built-in Toolsets

HolmesGPT includes pre-built integrations for popular monitoring and observability tools. Some work automatically with Kubernetes, while others require API keys or configuration.

## Getting Started

💡 **New to HolmesGPT?** Start with [Kubernetes](kubernetes.md) and [Prometheus](prometheus.md) for basic cluster monitoring.

**Quick Setup Process:**

1. **Choose toolsets** from the categories below that match your infrastructure
2. **Configure authentication** - some need API keys, others work automatically
3. **Run a test investigation** to verify data access

---

## Kubernetes & Container Platforms

Core integrations for container orchestration and deployment platforms.

<div class="grid cards" markdown>

-   [:simple-kubernetes:{ .lg .middle } **Kubernetes**](kubernetes.md)

    ---

    Essential toolset for pod, service, and cluster troubleshooting

-   [:material-microsoft-azure:{ .lg .middle } **Azure Kubernetes Service**](aks.md)

    ---

    Azure-specific Kubernetes cluster insights

-   [:simple-argo:{ .lg .middle } **ArgoCD**](argocd.md)

    ---

    GitOps deployment status and application health

-   [:simple-docker:{ .lg .middle } **Docker**](docker.md)

    ---

    Container runtime and image troubleshooting

-   [:material-package:{ .lg .middle } **Helm**](helm.md)

    ---

    Kubernetes package manager troubleshooting

-   [:material-heart-pulse:{ .lg .middle } **AKS Node Health**](aks-node-health.md)

    ---

    Azure Kubernetes node diagnostics

</div>

## Monitoring & Observability

Metrics, alerts, and performance monitoring integrations.

<div class="grid cards" markdown>

-   [:simple-prometheus:{ .lg .middle } **Prometheus**](prometheus.md)

    ---

    Metrics queries and alerting analysis

-   [:simple-datadog:{ .lg .middle } **DataDog**](datadog.md)

    ---

    Full-stack monitoring and APM insights

-   [:simple-newrelic:{ .lg .middle } **New Relic**](newrelic.md)

    ---

    Application performance and infrastructure monitoring

-   [:material-robot:{ .lg .middle } **Robusta**](robusta.md)

    ---

    Kubernetes monitoring and automation platform

</div>

## Logs & Analytics

Log aggregation, search, and distributed tracing tools.

<div class="grid cards" markdown>

-   [:simple-grafana:{ .lg .middle } **Loki**](grafanaloki.md)

    ---

    Log aggregation and search via Grafana

-   [:simple-grafana:{ .lg .middle } **Tempo**](grafanatempo.md)

    ---

    Distributed tracing analysis

-   [:simple-opensearch:{ .lg .middle } **OpenSearch**](opensearch-logs.md)

    ---

    Enterprise search and analytics platform

-   [:material-chart-line:{ .lg .middle } **Coralogix**](coralogix-logs.md)

    ---

    Cloud-native observability platform

</div>

## Cloud Providers

Cloud-specific services and database integrations.

<div class="grid cards" markdown>

-   [:material-aws:{ .lg .middle } **AWS**](aws.md)

    ---

    Amazon Web Services resources and APIs

-   [:material-database:{ .lg .middle } **Azure SQL Database**](azure-sql.md)

    ---

    Azure database performance and health

-   [:simple-mongodb:{ .lg .middle } **MongoDB Atlas**](mongodb-atlas.md)

    ---

    Cloud database monitoring and diagnostics

</div>

## Collaboration & Documentation

Knowledge bases, issue tracking, and team communication tools.

<div class="grid cards" markdown>

-   [:material-github:{ .lg .middle } **GitHub**](github.md)

    ---

    Repository insights and issue analysis

-   [:simple-confluence:{ .lg .middle } **Confluence**](confluence.md)

    ---

    Team knowledge base and documentation

-   [:material-ticket:{ .lg .middle } **ServiceNow**](servicenow.md)

    ---

    IT service management and incident tracking

-   [:simple-notion:{ .lg .middle } **Notion**](notion.md)

    ---

    Workspace documentation and knowledge sharing

-   [:material-forum:{ .lg .middle } **Slab**](slab.md)

    ---

    Modern team hub for documentation and knowledge

</div>

## Message Queues

Messaging systems and distributed streaming platforms.

<div class="grid cards" markdown>

-   [:simple-apachekafka:{ .lg .middle } **Kafka**](kafka.md)

    ---

    Distributed streaming platform monitoring

-   [:simple-rabbitmq:{ .lg .middle } **RabbitMQ**](rabbitmq.md)

    ---

    Message broker performance and queue analysis

</div>

## Utilities

General-purpose utility toolsets for specialized functions.

<div class="grid cards" markdown>

-   [:material-bash:{ .lg .middle } **Bash**](bash.md)

    ---

    Secure command-line tool execution and system analysis

-   [:material-clock:{ .lg .middle } **Datetime**](datetime.md)

    ---

    Time-based utilities for investigations

-   [:material-web:{ .lg .middle } **Internet**](internet.md)

    ---

    External connectivity and web resource checks

</div>

---

## Additional Resources

- **[Custom Toolsets](../custom-toolsets.md)** - Create your own integrations
- **[Remote MCP Servers](../remote-mcp-servers.md)** - Connect external MCP servers
- **[Adding Permissions](../permissions.md)** - Configure RBAC for additional resources
