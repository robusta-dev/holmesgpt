# Grafana Loki

By enabling this toolset, HolmesGPT will fetch pod logs from [Loki](https://grafana.com/oss/loki/). Loki can be accessed directly or by proxying through a [Grafana](https://grafana.com/oss/grafana/) instance.

You **should** enable this toolset to replace the default Kubernetes logs toolset if all your kubernetes/pod logs are consolidated inside Loki. It will make it easier for HolmesGPT to fetch incident logs, including the ability to precisely consult past logs.

!!! warning "Logging Toolsets"
    Only one logging toolset should be enabled at a time. If you enable this toolset, disable the default `kubernetes/logs` toolset.

## Proxying through Grafana

This is the recommended approach because we intend to add more capabilities to the toolset that are only available with Grafana.

### Prerequisites

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

# List the loki data sources
curl -s -u <username>:<password> http://localhost:3000/api/datasources | jq '.[] | select(.type == "loki")'
```

This will return something like:

```json
{
    "id": 2,
    "uid": "klja8hsa-8a9c-4b35-1230-7baab22b02ee",
    "orgId": 1,
    "name": "Loki-kubernetes",
    "type": "loki",
    "typeName": "Loki",
    "typeLogoUrl": "/public/app/plugins/datasource/loki/img/loki_icon.svg",
    "access": "proxy",
    "url": "http://loki.loki:3100",
    "user": "",
    "database": "",
    "basicAuth": false,
    "isDefault": false,
    "jsonData": {
        "httpHeaderName1": "admin",
        "httpHeaderName2": "X-Scope-OrgID",
        "tlsSkipVerify": true
    },
    "readOnly": false
}
```

In this case, the Loki datasource UID is `klja8hsa-8a9c-4b35-1230-7baab22b02ee`.

### Configuration (Grafana Proxy)

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      grafana/loki:
        enabled: true
        config:
          api_key: <your grafana API key>
          url: https://xxxxxxx.grafana.net # Your Grafana cloud account URL
          grafana_datasource_uid: <the UID of the loki data source in Grafana>

      kubernetes/logs:
        enabled: false # HolmesGPT's default logging mechanism MUST be disabled
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        grafana/loki:
          enabled: true
          config:
            api_key: <your grafana API key>
            url: https://xxxxxxx.grafana.net # Your Grafana cloud account URL
            grafana_datasource_uid: <the UID of the loki data source in Grafana>

        kubernetes/logs:
          enabled: false # HolmesGPT's default logging mechanism MUST be disabled
    ```

## Direct Connection

The toolset can directly connect to a Loki instance without proxying through a Grafana instance. This is done by not setting the `grafana_datasource_uid` field. Not setting this field makes HolmesGPT assume that it is directly connecting to Loki.

### Configuration (Direct Connection)

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      grafana/loki:
        enabled: true
        config:
          url: http://loki.logging
          headers:
            X-Scope-OrgID: "<tenant id>" # Set the X-Scope-OrgID if loki multitenancy is enabled

      kubernetes/logs:
        enabled: false # HolmesGPT's default logging mechanism MUST be disabled
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        grafana/loki:
          enabled: true
          config:
            url: http://loki.logging
            headers:
              X-Scope-OrgID: "<tenant id>" # Set the X-Scope-OrgID if loki multitenancy is enabled

        kubernetes/logs:
          enabled: false # HolmesGPT's default logging mechanism MUST be disabled
    ```

## Advanced Configuration

### Search Labels

You can tweak the labels used by the toolset to identify kubernetes resources. This is only needed if your Loki logs settings for `pod`, and `namespace` differ from the defaults.

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**:

    ```yaml
    toolsets:
      grafana/loki:
        enabled: true
        config:
          url: ...
          labels:
              pod: "pod"
              namespace: "namespace"
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        grafana/loki:
          enabled: true
          config:
            url: ...
            labels:
                pod: "pod"
                namespace: "namespace"
    ```

Use the following commands to list Loki's labels and determine which ones to use:

```bash
# Make Loki accessible locally
kubectl port-forward svc/loki 3100:3100

# List all labels. You may have to add the -H 'X-Scope-OrgID:<org id>' option with a valid org id
curl http://localhost:3100/loki/api/v1/labels
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| fetch_pod_logs | Fetches pod logs from Loki |
