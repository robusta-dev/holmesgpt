# Anthropic

Configure HolmesGPT to use Anthropic's Claude models.

## Setup

Get an [Anthropic API key](https://support.anthropic.com/en/articles/8114521-how-can-i-access-the-anthropic-api).

## Configuration

### Using Environment Variables

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
holmes ask "what pods are unhealthy and why?" --model="anthropic/claude-3-opus-20240229"
```

### Using CLI Arguments

```bash
holmes ask "what pods are unhealthy and why?" --model="anthropic/claude-3-opus-20240229" --api-key="your-anthropic-api-key"
```

## Available Models

```bash
# Claude 3 Opus
holmes ask "analyze this complex deployment failure" --model="anthropic/claude-3-opus-20240229"

# Claude 3 Sonnet
holmes ask "what pods are failing?" --model="anthropic/claude-3-sonnet-20240229"

# Claude 3 Haiku
holmes ask "cluster status summary" --model="anthropic/claude-3-haiku-20240307"
```

## Troubleshooting

**Authentication Error**
```
Error: Invalid Anthropic API key
```
- Verify your API key is correct
- Check that your account has sufficient credits

**Model Not Found**
```
Error: Model not available
```
- Verify the model name is spelled correctly
- Check that you have access to the requested model

**Rate Limits**
```
Error: Rate limit exceeded
```
- Wait for the rate limit to reset or upgrade your account
