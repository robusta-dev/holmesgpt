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
# GPT-4o (default)
holmes ask "what pods are failing?"

# GPT-4o mini (faster, but results are not as accurate)
holmes ask "what pods are failing?" --model="gpt-4o-mini"

# GPT-5
holmes ask "what pods are failing?" --model="gpt-5"
```

## GPT-5 Reasoning Effort

When using GPT-5 models, you can control the reasoning effort level by setting the `REASONING_EFFORT` environment variable. This allows you to balance between response quality and processing time/cost.

```bash
# Use minimal reasoning effort for faster responses
export REASONING_EFFORT="minimal"
holmes ask "what pods are failing?" --model="gpt-5"

# Use default reasoning effort
export REASONING_EFFORT="medium"
holmes ask "what pods are failing?" --model="gpt-5"

# Use high reasoning effort for complex investigations
export REASONING_EFFORT="high"
holmes ask "what pods are failing?" --model="gpt-5"
```

Available reasoning effort levels:

- `minimal` - Fastest responses, suitable for simple queries
- `low` - Balance between speed and quality
- `medium` - Standard reasoning depth (default)
- `high` - Deeper reasoning for complex problems

For more details on reasoning effort levels, refer to the [OpenAI documentation](https://platform.openai.com/docs/).

## Additional Resources

HolmesGPT uses the LiteLLM API to support OpenAI provider. Refer to [LiteLLM OpenAI docs](https://litellm.vercel.app/docs/providers/openai){:target="_blank"} for more details.
