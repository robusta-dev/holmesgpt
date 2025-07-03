# Ollama

Configure HolmesGPT to use local models with Ollama.

!!! warning
    Ollama support is experimental. Tool-calling capabilities are limited and may produce inconsistent results.

## Setup

1. Download Ollama from [ollama.com](https://ollama.com/)
2. Start Ollama: `ollama serve`
3. Download models: `ollama pull <model-name>`

## Configuration

```bash
export OLLAMA_API_BASE="http://localhost:11434"
holmes ask "what pods are failing?" --model="ollama_chat/<your-ollama-model>"
```
