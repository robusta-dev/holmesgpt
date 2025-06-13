# OpenAI

Configure HolmesGPT to use OpenAI's GPT models.

## Setup

Get a paid [OpenAI API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key).

!!! note
    This requires a paid OpenAI API key, not a ChatGPT Plus subscription.

## Configuration

### Using CLI Arguments

```bash
holmes ask --api-key="your-openai-api-key" "what pods are crashing in my cluster and why?"
```

### Using Environment Variables

```bash
export OPENAI_API_KEY="your-openai-api-key"
holmes ask "what pods are crashing in my cluster and why?"
```

## Available Models

OpenAI is the default provider. Specify models with the `--model` flag:

```bash
# Default model (gpt-4o)
holmes ask "what pods are failing?"

# Specific models
holmes ask "what pods are failing?" --model="gpt-4"
holmes ask "what pods are failing?" --model="gpt-3.5-turbo"
```

## Troubleshooting

**Invalid API Key**
```
Error: Invalid OpenAI API key
```
- Verify your API key is correct
- Ensure your account has sufficient credits

**Rate Limits**
```
Error: Rate limit exceeded
```
- Wait for the limit to reset or upgrade your OpenAI account

**Insufficient Credits**
```
Error: You exceeded your current quota
```
- Add payment method to your OpenAI account
