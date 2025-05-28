# Built-in Toolsets

HolmesGPT comes with 18+ pre-built integrations that automatically fetch and analyze data from your infrastructure and applications.

## Core Infrastructure

Essential integrations for Kubernetes and cloud environments:

- **[Kubernetes](kubernetes.md)** - Pods, services, events, logs (enabled by default)
- **[AWS](aws.md)** - EC2, ECS, CloudWatch, and other AWS services
- **[Docker](docker.md)** - Container information and logs
- **[Helm](helm.md)** - Helm chart and release information

## Monitoring & Observability

Integrations for metrics, logs, and traces:

- **[Prometheus](prometheus.md)** - Metrics collection and querying
- **[Grafana (Loki & Tempo)](grafana.md)** - Log aggregation and distributed tracing
- **[Coralogix](coralogix.md)** - Cloud-native observability platform
- **[OpenSearch](opensearch.md)** - Search and analytics engine

## Application Services

Message queues and application infrastructure:

- **[Kafka](kafka.md)** - Apache Kafka cluster information
- **[RabbitMQ](rabbitmq.md)** - Message broker monitoring

## DevOps Tools

CI/CD and deployment management:

- **[ArgoCD](argocd.md)** - GitOps deployment status and history
- **[Robusta](robusta.md)** - Robusta platform integration

## Knowledge Management

Documentation and knowledge bases:

- **[Confluence](confluence.md)** - Atlassian Confluence integration
- **[Notion](notion.md)** - Notion workspace integration
- **[Slab](slab.md)** - Team knowledge base

## Utility Toolsets

Helper tools for investigations:

- **[Internet](internet.md)** - Web searches and external data
- **[Datetime](datetime.md)** - Time and date utilities

## Configuration

Most toolsets fall into these categories:

### Enabled by Default
Some toolsets work automatically:
- Kubernetes resources and logs
- Docker container information
- Basic datetime utilities

### Requires Configuration
Most external services need API keys or credentials:
- Cloud providers (AWS)
- Monitoring tools (Prometheus, Grafana)
- Third-party services (Confluence, Notion)

### Optional Setup
Some toolsets enhance investigations but aren't required:
- Knowledge management tools
- Specialized monitoring platforms

## Next Steps

1. **Review** the toolsets relevant to your infrastructure
2. **Configure** authentication for external services
3. **Test** investigations to see which data sources are accessed

Click on any toolset above to see detailed configuration instructions.