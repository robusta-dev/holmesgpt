# Ollama

Configure HolmesGPT to use local models with Ollama.

!!! warning
    Ollama is supported, but buggy. We recommend using other models if you can, until Ollama tool-calling capabilities improve. Specifically, Ollama often calls tools with non-existent or missing parameters.

## Setup

1. Download Ollama from [ollama.ai](https://ollama.ai/)
2. Install following the instructions for your operating system
3. Start Ollama service:
   ```bash
   ollama serve
   ```

### Download Models

```bash
# Popular models for troubleshooting
ollama pull llama3.1
ollama pull codellama
ollama pull mistral
```

## Configuration

### Method 1: Ollama Native Format

```bash
export OLLAMA_API_BASE="http://localhost:11434"
holmes ask "what pods are unhealthy in my cluster?" --model="ollama_chat/llama3.1"
```

### Method 2: OpenAI-Compatible Format

```bash
# Note the v1 at the end
export OPENAI_API_BASE="http://localhost:11434/v1"
# Holmes requires OPENAI_API_KEY to be set but value does not matter
export OPENAI_API_KEY=123
holmes ask "what pods are unhealthy in my cluster?" --model="openai/llama3.1"
```

### Model Usage

```bash
# Using different models
holmes ask "pod analysis" --model="ollama_chat/llama3.1:8b"
holmes ask "yaml debugging" --model="ollama_chat/codellama:7b"
holmes ask "quick check" --model="ollama_chat/mistral:7b"
```

## Known Limitations

Current problems with Ollama:

1. **Missing parameters** - Tools called without required arguments
2. **Invalid parameters** - Non-existent parameter names
3. **Inconsistent behavior** - Results may vary between runs
4. **Limited function following** - May not follow tool schemas correctly

## Troubleshooting

**Ollama Not Running**
```
Error: Connection refused
```
- Start Ollama service: `ollama serve`
- Check if port 11434 is available
- Verify firewall settings

**Model Not Found**
```
Error: Model not found
```
- Pull the model: `ollama pull model-name`
- List available models: `ollama list`
- Check model name spelling

**Memory Issues**
```
Error: Out of memory
```
- Choose a smaller model
- Close other applications
- Add more RAM or use GPU acceleration

**Slow Performance**
```
Taking too long to respond
```
- Use smaller models (7B instead of 13B/70B)
- Enable GPU acceleration
- Increase CPU allocation: `export OLLAMA_NUM_THREAD=8`
