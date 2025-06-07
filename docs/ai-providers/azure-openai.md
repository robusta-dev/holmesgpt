# Azure OpenAI

Configure HolmesGPT to use Azure OpenAI Service.

## Setup

Create an [Azure OpenAI resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource).

## Configuration

### Required Environment Variables

```bash
export AZURE_API_VERSION="2024-02-15-preview"
export AZURE_API_BASE="https://my-org.openai.azure.com/"
export AZURE_API_KEY="your-azure-api-key"  # Optional, can use --api-key instead
```

### Usage

```bash
holmes ask "what pods are unhealthy and why?" --model=azure/<DEPLOYMENT_NAME> --api-key=<API_KEY>
```

Replace `<DEPLOYMENT_NAME>` with your actual Azure OpenAI deployment name.

## Environment Variables

- **AZURE_API_VERSION** - API version (e.g., `2024-02-15-preview`)
- **AZURE_API_BASE** - Your Azure endpoint URL (e.g., `https://my-org.openai.azure.com/`)
- **AZURE_API_KEY** - Your Azure API key (optional if passed via `--api-key`)

## Available Models

Azure OpenAI uses deployment names instead of model names:

```bash
# Using gpt-4 deployment
holmes ask "analyze cluster issues" --model=azure/gpt-4-deployment

# Using gpt-35-turbo deployment
holmes ask "quick cluster check" --model=azure/gpt-35-turbo-deployment
```

!!! note
    Model availability varies by region. Check your Azure portal for available models.

## Troubleshooting

**Authentication Errors**
```
Error: Azure authentication failed
```
- Verify environment variables are set correctly
- Check that your Azure OpenAI resource is deployed
- Ensure your API key has the correct permissions

**Deployment Not Found**
```
Error: Deployment not found
```
- Verify your deployment name is correct
- Check that the deployment is in the same region as your API base
- Ensure the deployment is fully deployed and running

**Regional Issues**
```
Error: Model not available in region
```
- Some models are only available in specific regions
- Consider deploying in a different region
