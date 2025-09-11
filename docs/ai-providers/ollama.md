# Ollama

Configure HolmesGPT to use local models with Ollama.

!!! warning
    Ollama support is experimental. Tool-calling capabilities are limited and may produce inconsistent results. Only [LiteLLM supported Ollama models](https://docs.litellm.ai/docs/providers/ollama#ollama-models){:target="_blank"} work with HolmesGPT.

## Setup

1. Download Ollama from [ollama.com](https://ollama.com/){:target="_blank"}
2. Start Ollama: `ollama serve`
3. Download models: `ollama pull <model-name>`

## Configuration

=== "Holmes CLI"

    ```bash
    export OLLAMA_API_BASE="http://localhost:11434"
    holmes ask "what pods are failing?" --model="ollama_chat/<your-ollama-model>"
    ```

=== "Holmes Helm Chart"

    **Configure Helm Values:**
    ```yaml
    # values.yaml
    additionalEnvVars:
      - name: OLLAMA_API_BASE
        value: "http://ollama-service:11434"

    # Configure at least one model using modelList
    modelList:
      ollama-llama3:
        api_base: "{{ env.OLLAMA_API_BASE }}"
        model: ollama_chat/llama3
        temperature: 1

      ollama-codellama:
        api_base: "{{ env.OLLAMA_API_BASE }}"
        model: ollama_chat/codellama
        temperature: 1

    # Optional: Set default model (use modelList key name, not the model path)
    config:
      model: "ollama-llama3"  # This refers to the key name in modelList above
    ```

    !!! note "Ollama Service"
        You'll need to deploy Ollama as a service in your cluster. The `OLLAMA_API_BASE` should point to your Ollama service endpoint.

=== "Robusta Helm Chart"

    **Configure Helm Values:**
    ```yaml
    # values.yaml
    holmes:
      additionalEnvVars:
        - name: OLLAMA_API_BASE
          value: "http://ollama-service:11434"

      # Configure at least one model using modelList
      modelList:
        ollama-llama3:
          api_base: "{{ env.OLLAMA_API_BASE }}"
          model: ollama_chat/llama3
          temperature: 1

        ollama-codellama:
          api_base: "{{ env.OLLAMA_API_BASE }}"
          model: ollama_chat/codellama
          temperature: 1

      # Optional: Set default model (use modelList key name, not the model path)
      config:
        model: "ollama-llama3"  # This refers to the key name in modelList above
    ```

    !!! note "Ollama Service"
        You'll need to deploy Ollama as a service in your cluster. The `OLLAMA_API_BASE` should point to your Ollama service endpoint.

### Using Environment Variables

```bash
export OLLAMA_API_BASE="http://localhost:11434"
export MODEL="ollama_chat/<your-ollama-model>"
holmes ask "what pods are failing?"
```


### Using CLI Parameters

You can also specify the model directly as a command-line parameter:

```bash
export OLLAMA_API_BASE="http://localhost:11434"
holmes ask "what pods are failing?" --model="ollama_chat/<your-ollama-model>"
```

## Additional Resources

HolmesGPT uses the LiteLLM API to support Ollama provider. Refer to [LiteLLM Ollama docs](https://docs.litellm.ai/docs/providers/ollama){:target="_blank"} for more details.
