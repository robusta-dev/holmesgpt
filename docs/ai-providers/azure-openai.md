# Azure OpenAI

Configure HolmesGPT to use Azure OpenAI Service.

## Setup

Create an [Azure OpenAI resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource){:target="_blank"}.

## Configuration

```bash
export AZURE_API_VERSION="2024-02-15-preview"
export AZURE_API_BASE="https://your-resource.openai.azure.com"
export AZURE_API_KEY="your-azure-api-key"

holmes ask "what pods are failing?" --model="azure/<your-deployment-name>"
```

## Using CLI Parameters

You can also pass the API key directly as a command-line parameter:

```bash
holmes ask "what pods are failing?" --model="azure/<your-deployment-name>" --api-key="your-api-key"
```

## Additional Resources

HolmesGPT uses the LiteLLM API to support Azure OpenAI provider. Refer to [LiteLLM Azure docs](https://litellm.vercel.app/docs/providers/azure){:target="_blank"} for more details.
