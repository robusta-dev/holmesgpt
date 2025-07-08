# Anthropic

Configure HolmesGPT to use Anthropic's Claude models.

## Setup

Get an [Anthropic API key](https://support.anthropic.com/en/articles/8114521-how-can-i-access-the-anthropic-api).

## Configuration

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
holmes ask "what pods are failing?" --model="anthropic/<your-claude-model>"
```
