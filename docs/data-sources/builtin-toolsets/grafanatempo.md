# Tempo

By enabling this toolset, HolmesGPT will be able to fetch trace information from Tempo to debug performance related issues, like high latency in your application.

## Configuration Reference

### All Configuration Options

| Field | Required | Description | Default |
|-------|----------|-------------|---------|
| `url` | Yes | Base URL for Tempo or Grafana instance | - |
| `api_key` | No | API key for authentication (Bearer token) | - |
| `grafana_datasource_uid` | No | UID of Tempo datasource in Grafana (enables proxy mode) | - |
| `headers` | No | Additional HTTP headers (e.g., for multi-tenancy) | - |
| `external_url` | No | External URL for generating links | - |
| `healthcheck` | No | Health check endpoint path | "ready" |
| `labels` | No | Custom label mappings for Kubernetes resources | See below |

### Default Label Mappings

```yaml
labels:
  pod: "k8s.pod.name"
  namespace: "k8s.namespace.name"
  deployment: "k8s.deployment.name"
  node: "k8s.node.name"
  service: "service.name"
```

## Proxying through Grafana

This is the recommended approach because we intend to add more capabilities to the toolset that are only available with Grafana.

### Prerequisites

A [Grafana service account token](https://grafana.com/docs/grafana/latest/administration/service-accounts/) with the following permissions:

* Basic role -> Viewer
* Data sources -> Reader

Check out this [video](https://www.loom.com/share/f969ab3af509444693802254ab040791?sid=aa8b3c65-2696-4f69-ae47-bb96e8e03c47) on creating a Grafana service account token.

**Getting Grafana URL**

You can find the Grafana URL required for Tempo in your Grafana cloud account settings.

**Obtaining the datasource UID**

You may have multiple Tempo data sources set up in Grafana. HolmesGPT uses a single Tempo datasource to fetch the traces and it needs to know the UID of this datasource.

A simple way to get the datasource UID is to access the Grafana API by running the following request:

```bash
# port forward if you are using Robusta's Grafana from your Kubernetes cluster
kubectl port-forward svc/robusta-grafana 3000:80
# List the Tempo data sources
curl -s -u <username>:<password> http://localhost:3000/api/datasources | jq '.[] | select(.type == "tempo")'
```

This will return something like:

```json
{
    "id": 3,
    "uid": "klja8hsa-8a9c-4b35-1230-7baab22b02ee",
    "orgId": 1,
    "name": "Tempo",
    "type": "tempo",
    "typeName": "Tempo",
    "typeLogoUrl": "/public/app/plugins/datasource/tempo/img/tempo_icon.svg",
    "access": "proxy",
    "url": "http://tempo-query-frontend.tempo:3100",
    "user": "",
    "database": "",
    "basicAuth": false,
    "isDefault": false,
    "jsonData": {
        "tlsSkipVerify": true
    },
    "readOnly": false
}
```

In this case, the Tempo datasource UID is `klja8hsa-8a9c-4b35-1230-7baab22b02ee`.

### Configuration (Grafana Proxy)

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**. Create the file if it doesn't exist:

    ```yaml
    toolsets:
      grafana/tempo:
        enabled: true
        config:
          api_key: "{{env.GRAFANA_API_KEY}}"  # Can use env variables
          url: <your grafana url> # e.g. https://acme-corp.grafana.net
          grafana_datasource_uid: <the UID of the tempo data source in Grafana>
          # Optional: Add headers for authentication or other purposes
          # headers:
          #   Custom-Header: "value"
    ```

    --8<-- "snippets/toolset_refresh_warning.md"

    To test, run:

    ```bash
    holmes ask "The payments DB is very slow, check tempo for any trace data"
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        grafana/tempo:
          enabled: true
          config:
            api_key: "{{env.GRAFANA_API_KEY}}"  # Can use env variables
            url: <your grafana url> # e.g. https://acme-corp.grafana.net
            grafana_datasource_uid: <the UID of the tempo data source in Grafana>
            # Optional: Custom label mappings (defaults shown)
            # labels:
            #   pod: "k8s.pod.name"
            #   namespace: "k8s.namespace.name"
            #   deployment: "k8s.deployment.name"
            #   node: "k8s.node.name"
            #   service: "service.name"
    ```

## Direct Connection

The toolset can directly connect to a Tempo instance without proxying through a Grafana instance. This is done by not setting the `grafana_datasource_uid` field. Not setting this field makes HolmesGPT assume that it is directly connecting to Tempo.

### Configuration (Direct Connection)

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**. Create the file if it doesn't exist:

    ```yaml
    toolsets:
      grafana/tempo:
        enabled: true
        config:
          url: http://tempo.monitoring:3200
          # Optional: API key for authentication
          # api_key: "{{env.TEMPO_API_KEY}}"
          # Optional: Headers for multi-tenancy or custom auth
          # headers:
          #   X-Scope-OrgID: "<tenant id>"
          # Optional: Custom health check endpoint
          # healthcheck: "ready"  # or "live"
    ```

    --8<-- "snippets/toolset_refresh_warning.md"

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        grafana/tempo:
          enabled: true
          config:
            url: http://tempo.monitoring:3200
            # Optional: API key for authentication
            # api_key: "{{env.TEMPO_API_KEY}}"
            # Optional: Headers for multi-tenancy or custom auth
            # headers:
            #   X-Scope-OrgID: "<tenant id>"
            # Optional: Custom health check endpoint
            # healthcheck: "ready"  # or "live"
    ```

## Advanced Configuration

### Search Labels

You can tweak the labels used by the toolset to identify Kubernetes resources. This is only needed if the trace labels differ from the defaults.

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**:

    ```yaml
    toolsets:
      grafana/tempo:
        enabled: true
        config:
          url: ...
          labels:
            pod: "k8s.pod.name"
            namespace: "k8s.namespace.name"
            deployment: "k8s.deployment.name"
            node: "k8s.node.name"
            service: "service.name"
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        grafana/tempo:
          enabled: true
          config:
            url: ...
            labels:
              pod: "k8s.pod.name"
              namespace: "k8s.namespace.name"
              deployment: "k8s.deployment.name"
              node: "k8s.node.name"
              service: "service.name"
    ```

## Example Configurations

### Multi-tenant Setup with Custom Labels

```yaml
toolsets:
  grafana/tempo:
    enabled: true
    config:
      url: http://tempo.monitoring:3200
      api_key: "{{env.TEMPO_API_KEY}}"
      headers:
        X-Scope-OrgID: "production"
      labels:
        pod: "custom.pod.label"
        namespace: "custom.ns.label"
        service: "svc.name"
```

### Environment Variables

You can use environment variables in your configuration with the `{{env.VARIABLE_NAME}}` syntax:

```yaml
toolsets:
  grafana/tempo:
    enabled: true
    config:
      url: "{{env.TEMPO_URL}}"
      api_key: "{{env.TEMPO_API_KEY}}"
      grafana_datasource_uid: "{{env.GRAFANA_TEMPO_DATASOURCE_UID}}"
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| fetch_tempo_traces_comparative_sample | Fetches statistics and samples of fast, slow, and typical traces for performance analysis. This is the primary tool for investigating performance issues. |
| search_traces_by_query | Search for traces using TraceQL query language (e.g., `{resource.service.name="api" && span.http.status_code=500}`). |
| search_traces_by_tags | Search for traces using logfmt-encoded tags (e.g., `resource.service.name="api" http.status_code="500"`). |
| query_trace_by_id | Retrieve detailed trace information by trace ID in OpenTelemetry format. |
| search_tag_names | Discover available tag names across traces, organized by scope (resource, span, intrinsic). |
| search_tag_values | Get all values for a specific tag (useful for discovering what values exist). |
| query_metrics_instant | Compute a single TraceQL metric value across a time range (e.g., average duration, error rate). |
| query_metrics_range | Get time series data from TraceQL metrics queries for graphing metrics over time. |
