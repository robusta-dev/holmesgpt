# Anthropic

Configure HolmesGPT to use Anthropic's Claude models.

## Setup

Get an [Anthropic API key](https://support.anthropic.com/en/articles/8114521-how-can-i-access-the-anthropic-api){:target="_blank"}.

## Configuration

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
holmes ask "what pods are failing?" --model="anthropic/<your-claude-model>"
```

## Using CLI Parameters

You can also pass the API key directly as a command-line parameter:

```bash
holmes ask "what pods are failing?" --model="anthropic/<your-claude-model>" --api-key="your-api-key"
```

## Additional Resources

HolmesGPT uses the LiteLLM API to support Anthropic provider. Refer to [LiteLLM Anthropic docs](https://litellm.vercel.app/docs/providers/anthropic){:target="_blank"} for more details.
