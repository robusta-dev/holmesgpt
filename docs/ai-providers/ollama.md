# Ollama

Configure HolmesGPT to use local models with Ollama.

!!! warning
    Ollama support is experimental. Tool-calling capabilities are limited and may produce inconsistent results. Only [LiteLLM supported Ollama models](https://docs.litellm.ai/docs/providers/ollama#ollama-models){:target="_blank"} work with HolmesGPT.

## Setup

1. Download Ollama from [ollama.com](https://ollama.com/){:target="_blank"}
2. Start Ollama: `ollama serve`
3. Download models: `ollama pull <model-name>`

## Configuration

```bash
export OLLAMA_API_BASE="http://localhost:11434"
holmes ask "what pods are failing?" --model="ollama_chat/<your-ollama-model>"
```

## Using CLI Parameters

You can also specify the model directly as a command-line parameter:

```bash
holmes ask "what pods are failing?" --model="ollama_chat/<your-ollama-model>"
```

## Additional Resources

HolmesGPT uses the LiteLLM API to support Ollama provider. Refer to [LiteLLM Ollama docs](https://docs.litellm.ai/docs/providers/ollama){:target="_blank"} for more details.
