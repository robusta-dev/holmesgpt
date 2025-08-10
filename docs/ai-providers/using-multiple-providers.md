# Using Multiple Providers

Configure multiple AI providers to give users flexibility in choosing models through the Robusta UI.

!!! note "UI Feature Only"
    Multiple provider configuration currently only impacts investigations run from the **Robusta UI**. When multiple providers are defined, users can select which model to use from a dropdown in the UI. This feature does not affect CLI usage or investigations triggered from other sources.

## Configuration

Configure multiple models using the `modelList` parameter in your Helm values, along with the necessary environment variables.

### Step 1: Create the Kubernetes Secret

First, create a secret with your API keys (only include the ones you need):

```bash
# Example with all providers - only include what you're using
kubectl create secret generic holmes-secrets \
  --from-literal=openai-api-key="sk-..." \
  --from-literal=anthropic-api-key="sk-ant-..." \
  --from-literal=azure-api-key="..." \
  --from-literal=aws-access-key-id="AKIA..." \
  --from-literal=aws-secret-access-key="..." \
  -n <namespace>

# Example with just OpenAI and Anthropic
kubectl create secret generic holmes-secrets \
  --from-literal=openai-api-key="sk-..." \
  --from-literal=anthropic-api-key="sk-ant-..." \
  -n <namespace>
```

### Step 2: Configure Helm Values

```yaml
# values.yaml
# Reference only the API keys you created in the secret
additionalEnvVars:
  - name: AZURE_API_KEY
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: azure-api-key
  - name: ANTHROPIC_API_KEY
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: anthropic-api-key
  - name: AWS_ACCESS_KEY_ID
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: aws-access-key-id
  - name: AWS_SECRET_ACCESS_KEY
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: aws-secret-access-key
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: openai-api-key

# Configure the model list using the environment variables
modelList:
  # Standard OpenAI
  openai-4o:
    api_key: "{{ env.OPENAI_API_KEY }}"
    model: openai/gpt-4o
    temperature: 0

  # Azure OpenAI Models
  azure-4o:
    api_key: "{{ env.AZURE_API_KEY }}"
    model: azure/gpt-4o
    api_base: https://your-resource.openai.azure.com/
    api_version: "2025-01-01-preview"
    temperature: 0

  azure-gpt-5:
    api_key: "{{ env.AZURE_API_KEY }}"
    model: azure/gpt-5-chat
    api_base: https://your-resource.openai.azure.com/
    api_version: "2025-01-01-preview"
    temperature: 1 # only 1 is supported for gpt-5 models

  # Anthropic Models
  claude-sonnet-4:
    api_key: "{{ env.ANTHROPIC_API_KEY }}"
    model: claude-sonnet-4-20250514
    temperature: 1
    thinking:
      budget_tokens: 10000
      type: enabled

  # AWS Bedrock
  bedrock-claude:
    aws_access_key_id: "{{ env.AWS_ACCESS_KEY_ID }}"
    aws_region_name: eu-south-2
    aws_secret_access_key: "{{ env.AWS_SECRET_ACCESS_KEY }}"
    model: bedrock/eu.anthropic.claude-sonnet-4-20250514-v1:0
    temperature: 1
    thinking:
      budget_tokens: 10000
      type: enabled
```


## Model Parameters

Each model in `modelList` can accept any parameter supported by LiteLLM for that provider. The `model` parameter is required, while authentication requirements vary by provider. Any additional LiteLLM parameters will be passed directly through to the provider.

### Required Parameter
- `model`: Model identifier (provider-specific format)

### Common Parameters
- `api_key`: API key for authentication where required (can use `{{ env.VAR_NAME }}` syntax)
- `temperature`: Creativity level (0-2, lower is more deterministic)

### Additional Parameters

You can pass any LiteLLM-supported parameter for your provider. Examples include:

- **Azure**: `api_base`, `api_version`, `deployment_id`
- **Anthropic**: `thinking` (with `budget_tokens` and `type`)
- **AWS Bedrock**: `aws_access_key_id`, `aws_secret_access_key`, `aws_region_name`, `aws_session_token`
- **Google Vertex**: `vertex_project`, `vertex_location`

Refer to [LiteLLM documentation](https://docs.litellm.ai/docs/providers) for the complete list of parameters supported by each provider.

## User Experience

When multiple models are configured:

1. Users see a **model selector dropdown** in the Robusta UI
2. Each model appears with its configured name (e.g., "azure-4o", "claude-sonnet-4")
3. Users can switch between models for different investigations

## Best Practices

1. **Use descriptive names**: Name models clearly (e.g., `fast-gpt4`, `accurate-claude`, `budget-mini`)
2. **Secure API keys**: Always use Kubernetes secrets for API keys

## Limitations

- **UI Only**: Model selection currently only works in the Robusta UI
- **No automatic failover**: If a selected model fails, users must manually switch

## See Also

- [UI Installation](../installation/ui-installation.md)
- [Helm Configuration](../reference/helm-configuration.md)
- Individual provider documentation for specific configuration details
