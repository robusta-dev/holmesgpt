# OpenAI

Configure HolmesGPT to use OpenAI's GPT models.

## Setup

Get a paid [OpenAI API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key){:target="_blank"}.

!!! note
    Requires a paid OpenAI API key, not a ChatGPT Plus subscription.

## Configuration

```bash
export OPENAI_API_KEY="your-openai-api-key"
holmes ask "what pods are failing?"
```

## Using CLI Parameters

You can also pass the API key directly as a command-line parameter:

```bash
holmes ask "what pods are failing?" --api-key="your-api-key"
```

## Available Models

```bash
# GPT-4o (default, recommended)
holmes ask "what pods are failing?"

# GPT-4o mini (faster, but results are not as accurate)
holmes ask "what pods are failing?" --model="gpt-4o-mini"
```

## Additional Resources

HolmesGPT uses the LiteLLM API to support OpenAI provider. Refer to [LiteLLM OpenAI docs](https://litellm.vercel.app/docs/providers/openai){:target="_blank"} for more details.
