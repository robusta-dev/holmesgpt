# OpenAI-Compatible Models

Configure HolmesGPT to use any OpenAI-compatible API.

!!! warning "Function Calling Required"
    Your model and inference server must support function calling (tool calling). Models that lack this capability may produce incorrect results.

## Requirements

- **Function calling support** - OpenAI-style tool calling
- **OpenAI-compatible API** - Standard endpoints and request/response format

## Supported Inference Servers

- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- [LocalAI](https://localai.io/)
- [Text Generation WebUI](https://github.com/oobabooga/text-generation-webui) (with OpenAI extension)

## Configuration

```bash
export OPENAI_API_BASE="http://localhost:8000/v1"
export OPENAI_API_KEY="not-needed"
holmes ask "what pods are failing?" --model="openai/<your-model>"
```

## Setup Examples

### LocalAI

```bash
docker run -p 8080:8080 localai/localai:latest
export OPENAI_API_BASE="http://localhost:8080/v1"
```

### llama-cpp-python

```bash
pip install 'llama-cpp-python[server]'
python -m llama_cpp.server --model model.gguf --chat_format chatml
export OPENAI_API_BASE="http://localhost:8000/v1"
holmes ask "analyze my deployment" --model=openai/your-loaded-model
```
