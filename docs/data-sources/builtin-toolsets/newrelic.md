# New Relic

By enabling this toolset, HolmesGPT will be able to pull traces and logs from New Relic for investigations.

--8<-- "snippets/toolsets_that_provide_logging.md"

## Prerequisites

1. A New Relic API Key with necessary permissions to access traces and logs
2. Your New Relic Account ID

You can find these in your New Relic account under Administration > API keys and Account settings.

## Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**. Create the file if it doesn't exist:

    ```yaml
    toolsets:
      newrelic:
        enabled: true
        config:
          nr_api_key: "<your New Relic API key>"
          nr_account_id: "<your New Relic account ID>"

      kubernetes/logs:
        enabled: false  # Disable default Kubernetes logging if using New Relic for logs
    ```

    --8<-- "snippets/toolset_refresh_warning.md"

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        newrelic:
          enabled: true
          config:
            nr_api_key: "<your New Relic API key>"
            nr_account_id: "<your New Relic account ID>"

        kubernetes/logs:
          enabled: false  # Disable default Kubernetes logging if using New Relic for logs
    ```

--8<-- "snippets/toolset_capabilities_intro.md"

--8<-- "snippets/capabilities_table_header.md"
| `newrelic_get_logs` | Retrieve logs from New Relic for a specific application and time range |
| `newrelic_get_traces` | Retrieve traces from New Relic based on duration threshold or specific trace ID |

For more information, see the [New Relic API documentation](https://docs.newrelic.com/docs/apis/nerdgraph-api/).
