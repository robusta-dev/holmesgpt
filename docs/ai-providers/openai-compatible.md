# OpenAI-Compatible Models

Configure HolmesGPT to use any OpenAI-compatible API.

!!! warning "Function Calling Required"
    Your model and inference server must support function calling (tool calling). HolmesGPT cannot check if the LLM supports function-calling. Models that lack this capability may hallucinate answers instead of properly using tools.

## Requirements

1. **Function calling support** - The model must support OpenAI-style tool calling
2. **OpenAI-compatible API** - Standard endpoints and request/response format

### Compatible Inference Servers

**✅ Supported:**
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) - Supports function calling
- [Text Generation WebUI](https://github.com/oobabooga/text-generation-webui) - With OpenAI extension
- [LocalAI](https://localai.io/) - Full OpenAI compatibility
- [FastChat](https://github.com/lm-sys/FastChat) - OpenAI-compatible server

**❌ Not Supported:**
- [vLLM](https://github.com/vllm-project/vllm) - [No function calling support yet](https://github.com/vllm-project/vllm/issues/1869)

## Configuration

### Basic Setup

```bash
export OPENAI_API_BASE="http://localhost:8000/v1"
holmes ask "what pods are unhealthy and why?" --model=openai/<MODEL_NAME> --api-key=<API_KEY>
```

### Environment Variables

```bash
# Required: API base URL
export OPENAI_API_BASE="http://your-server:8000/v1"

# Optional: API key (use random value if not required)
export OPENAI_API_KEY="your-api-key-or-random-value"
```

## Common Setups

### llama-cpp-python Server

```bash
# Install with function calling support
pip install 'llama-cpp-python[server]'

# Start server with function calling enabled
python -m llama_cpp.server \
  --model model.gguf \
  --host 0.0.0.0 \
  --port 8000 \
  --chat_format chatml
```

Configure HolmesGPT:

```bash
export OPENAI_API_BASE="http://localhost:8000/v1"
export OPENAI_API_KEY="not-needed"
holmes ask "what's wrong with my pods?" --model=openai/model
```

### LocalAI

```bash
# Start LocalAI
docker run -p 8080:8080 --name local-ai -ti localai/localai:latest

# Download a model
curl http://localhost:8080/models/apply -H "Content-Type: application/json" -d '{
  "id": "model-gallery@llama3-instruct",
  "name": "llama3-instruct"
}'
```

Configure HolmesGPT:

```bash
export OPENAI_API_BASE="http://localhost:8080/v1"
export OPENAI_API_KEY="not-needed"
holmes ask "cluster health check" --model=openai/llama3-instruct
```

### Text Generation WebUI

```bash
# Start with OpenAI extension
python server.py --extensions openai --listen --api-port 5000
```

Configure HolmesGPT:

```bash
export OPENAI_API_BASE="http://localhost:5000/v1"
export OPENAI_API_KEY="not-needed"
holmes ask "analyze my deployment" --model=openai/your-loaded-model
```

## Testing Function Calling

Verify your setup:

```bash
# Simple test that should call kubectl tools
holmes ask "list all pods in default namespace" --model=openai/your-model

# Check if tools are being called properly
holmes ask "describe the first pod you find" --model=openai/your-model
```

### Expected Behavior

✅ **Working correctly:**
- HolmesGPT calls kubectl commands
- Returns actual cluster data
- Provides specific pod names and details

❌ **Not working:**
- Generic responses without real data
- "I cannot access your cluster" messages
- Hallucinated pod names or information

## Troubleshooting

**Model Doesn't Call Tools**
```
Response: "I cannot access your Kubernetes cluster"
```
- Verify the model supports function calling
- Check if the inference server properly handles tool calls
- Try a different model known to support function calling

**Invalid Tool Parameters**
```
Error: Tool called with missing required parameter
```
- The model may not understand the tool schema properly
- Try a larger or more capable model
- Check inference server logs for schema issues

**Connection Refused**
```
Error: Connection refused to localhost:8000
```
- Ensure the inference server is running
- Check the port number and host
- Verify firewall settings

**API Compatibility Issues**
```
Error: Unexpected response format
```
- Verify the server implements OpenAI-compatible API
- Check API version compatibility
- Review server logs for errors
