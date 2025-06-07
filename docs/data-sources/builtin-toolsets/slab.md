# Slab

By enabling this toolset, HolmesGPT will be able to consult runbooks from Slab pages.

Retrieve your Slab [API token](https://help.slab.com/en/articles/6545629-developer-tools-api-webhooks) prior to configuring this toolset. Do note that Slab API is only available for Slab premium users. See [here](https://help.slab.com/en/articles/6545629-developer-tools-api-webhooks).

## Configuration

=== "Holmes CLI"

    First create the following environment variable:

    ```bash
    export SLAB_API_KEY="<your slab API key>"
    ```

    Then add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      slab:
        enabled: true
    ```

    To test, run:

    ```bash
    holmes ask "Why is my pod failing, if its a crashloopbackoff use the runbooks from slab"
    ```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| fetch_slab_document | Fetch a document from slab. Use this to fetch runbooks if they are present before starting your investigation. |
