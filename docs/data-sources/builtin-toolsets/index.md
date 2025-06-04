# Built-in Toolsets

Holmes allows defining integrations (toolsets) that fetch data from external sources. Some toolsets are enabled by default, while others require the user to add their own configuration/credentials.

## Available Toolsets

<div class="grid cards" markdown>

-   **ArgoCD**

    ---

    Integration with ArgoCD for GitOps deployment information.

    [:octicons-arrow-right-24: Configuration](argocd.md)

-   **AWS**

    ---

    Amazon Web Services integration for cloud resources.

    [:octicons-arrow-right-24: Configuration](aws.md)

-   **Confluence**

    ---

    Atlassian Confluence integration for documentation access.

    [:octicons-arrow-right-24: Configuration](confluence.md)

-   **Coralogix logs**

    ---

    Coralogix cloud-native observability platform integration.

    [:octicons-arrow-right-24: Configuration](coralogix.md)

-   **Datetime**

    ---

    Time and date utilities for investigations.

    [:octicons-arrow-right-24: Configuration](datetime.md)

-   **Docker**

    ---

    Docker container information and management.

    [:octicons-arrow-right-24: Configuration](docker.md)

-   **Grafana Loki**

    ---

    Grafana Loki log aggregation system integration.

    [:octicons-arrow-right-24: Configuration](grafana.md)

-   **Grafana Tempo**

    ---

    Grafana Tempo distributed tracing integration.

    [:octicons-arrow-right-24: Configuration](grafana.md)

-   **Helm**

    ---

    Helm chart and release information.

    [:octicons-arrow-right-24: Configuration](helm.md)

-   **Internet**

    ---

    Web searches and external data access.

    [:octicons-arrow-right-24: Configuration](internet.md)

-   **Kafka**

    ---

    Apache Kafka cluster information and monitoring.

    [:octicons-arrow-right-24: Configuration](kafka.md)

-   **Kubernetes**

    ---

    Core Kubernetes resources, events, and logs.

    [:octicons-arrow-right-24: Configuration](kubernetes.md)

-   **Notion**

    ---

    Notion workspace integration for documentation.

    [:octicons-arrow-right-24: Configuration](notion.md)

-   **OpenSearch logs**

    ---

    OpenSearch log aggregation and search integration.

    [:octicons-arrow-right-24: Configuration](opensearch.md)

-   **OpenSearch status**

    ---

    OpenSearch cluster status and health monitoring.

    [:octicons-arrow-right-24: Configuration](opensearch.md)

-   **Prometheus**

    ---

    Prometheus metrics collection and querying.

    [:octicons-arrow-right-24: Configuration](prometheus.md)

-   **RabbitMQ**

    ---

    RabbitMQ message broker monitoring and management.

    [:octicons-arrow-right-24: Configuration](rabbitmq.md)

-   **Robusta**

    ---

    Robusta platform integration for enhanced Kubernetes monitoring.

    [:octicons-arrow-right-24: Configuration](robusta.md)

-   **Slab**

    ---

    Slab team knowledge base integration.

    [:octicons-arrow-right-24: Configuration](slab.md)

</div>

## Getting Started

1. **Review** the toolsets relevant to your infrastructure
2. **Configure** authentication for external services
3. **Test** investigations to see which data sources are accessed

Some toolsets work automatically with Kubernetes, while external services require API keys or credentials to be configured.
