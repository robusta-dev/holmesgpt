# Azure OpenAI

Configure HolmesGPT to use Azure OpenAI Service.

## Setup

Create an [Azure OpenAI resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource).

## Configuration

```bash
export AZURE_API_VERSION="2024-02-15-preview"
export AZURE_API_BASE="https://your-resource.openai.azure.com/"
export AZURE_API_KEY="your-azure-api-key"

holmes ask "what pods are failing?" --model="azure/<your-deployment-name>"
```
