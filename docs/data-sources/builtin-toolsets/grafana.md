# Grafana

## Loki

By enabling this toolset, HolmesGPT will fetch pod logs from [Loki](https://grafana.com/oss/loki/). Loki can be accessed directly or by proxying through a [Grafana](https://grafana.com/oss/grafana/) instance.

You **should** enable this toolset to replace the default Kubernetes logs toolset if all your kubernetes/pod logs are consolidated inside Loki. It will make it easier for HolmesGPT to fetch incident logs, including the ability to precisely consult past logs.

!!! warning "Logging Toolsets"
    Only one logging toolset should be enabled at a time. If you enable this toolset, disable the default `kubernetes/logs` toolset.

### Proxying through Grafana

This is the recommended approach because we intend to add more capabilities to the toolset that are only available with Grafana.

#### Prerequisites

A [Grafana service account token](https://grafana.com/docs/grafana/latest/administration/service-accounts/) with the following permissions:

* Basic role -> Viewer
* Data sources -> Reader

Check out this [video](https://www.loom.com/share/f969ab3af509444693802254ab040791?sid=aa8b3c65-2696-4f69-ae47-bb96e8e03c47) on creating a Grafana service account token.

**Getting Grafana URL**

You can find the Grafana URL required for Loki in your Grafana cloud account settings.

**Obtaining the datasource UID**

You may have multiple Loki data sources setup in Grafana. HolmesGPT uses a single Loki datasource to fetch the logs and it needs to know the UID of this datasource.

A simple way to get the datasource UID is to access the Grafana API by running the following request:

```bash
# port forward if you are using Robusta's grafana from your kubernetes cluster
kubectl port-forward svc/robusta-grafana 3000:80
# List the Loki data sources
curl -s -u <username>:<password> http://localhost:3000/api/datasources | jq '.[] | select(.type == "loki")'
```

#### Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      grafana/loki:
        enabled: true
        config:
          grafana_api_key: "<your grafana service account token>"
          grafana_url: "https://your-grafana-instance.com"
          datasource_uid: "<loki datasource UID>"

      kubernetes/logs:
        enabled: false # Disable default Kubernetes logging
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        grafana/loki:
          enabled: true
          config:
            grafana_api_key: "<your grafana service account token>"
            grafana_url: "https://your-grafana-instance.com"
            datasource_uid: "<loki datasource UID>"

        kubernetes/logs:
          enabled: false # Disable default Kubernetes logging
    ```

## Tempo

By enabling this toolset, HolmesGPT will be able to fetch trace information from Grafana Tempo to debug performance related issues, like high latency in your application.

### Proxying through Grafana

This is the recommended approach because we intend to add more capabilities to the toolset that are only available with Grafana.

#### Prerequisites

A [Grafana service account token](https://grafana.com/docs/grafana/latest/administration/service-accounts/) with the following permissions:

* Basic role -> Viewer
* Data sources -> Reader

Check out this [video](https://www.loom.com/share/f969ab3af509444693802254ab040791?sid=aa8b3c65-2696-4f69-ae47-bb96e8e03c47) on creating a Grafana service account token.

**Getting Grafana URL**

You can find the Grafana URL required for Tempo in your Grafana cloud account settings.

**Obtaining the datasource UID**

You may have multiple Tempo data sources setup in Grafana. HolmesGPT uses a single Tempo datasource to fetch the traces and it needs to know the UID of this datasource.

A simple way to get the datasource UID is to access the Grafana API by running the following request:

```bash
# port forward if you are using Robusta's grafana from your kubernetes cluster
kubectl port-forward svc/robusta-grafana 3000:80
# List the Tempo data sources
curl -s -u <username>:<password> http://localhost:3000/api/datasources | jq '.[] | select(.type == "tempo")'
```

#### Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      grafana/tempo:
        enabled: true
        config:
          grafana_api_key: "<your grafana service account token>"
          grafana_url: "https://your-grafana-instance.com"
          datasource_uid: "<tempo datasource UID>"
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        grafana/tempo:
          enabled: true
          config:
            grafana_api_key: "<your grafana service account token>"
            grafana_url: "https://your-grafana-instance.com"
            datasource_uid: "<tempo datasource UID>"
    ```

## Capabilities

### Loki Capabilities

| Tool Name | Description |
|-----------|-------------|
| fetch_loki_logs_for_resource | Fetch logs from Loki for specified Kubernetes resources |
| fetch_loki_logs_for_resource_wildcard | Fetch logs using wildcard patterns |

### Tempo Capabilities

| Tool Name | Description |
|-----------|-------------|
| fetch_tempo_trace_by_id | Fetch a specific trace by its ID |
| fetch_tempo_traces_by_deployment | Fetch traces for a specific deployment |
