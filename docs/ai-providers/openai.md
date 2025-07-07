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

## Available Models

```bash
# GPT-4o (default, recommended)
holmes ask "what pods are failing?"

# GPT-4o mini (faster, cheaper)
holmes ask "what pods are failing?" --model="gpt-4o-mini"
```
