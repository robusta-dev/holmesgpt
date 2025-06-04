# Gemini

Configure HolmesGPT to use Google's Gemini models via Google AI Studio.

## Setup

Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

## Configuration

### Environment Variables

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

### Usage

```bash
holmes ask "what pods are unhealthy and why?" --model=gemini/<MODEL_NAME>
```

## Available Models

```bash
# Gemini Pro (standard model)
holmes ask "analyze cluster issues" --model=gemini/gemini-pro

# Gemini 1.5 Flash (fast and efficient)
holmes ask "quick diagnostics" --model=gemini/gemini-1.5-flash

# Gemini 1.5 Pro (most capable)
holmes ask "complex analysis" --model=gemini/gemini-1.5-pro
```

## Troubleshooting

**API Key Issues**
```
Error: Invalid API key
```
- Verify your API key is correct and active
- Check that you've enabled the Gemini API
- Ensure the key hasn't been revoked or expired

**Rate Limiting**
```
Error: Rate limit exceeded
```
- Wait for the rate limit to reset
- Consider upgrading to a paid tier for higher limits

**Model Not Found**
```
Error: Model not available
```
- Verify the model name is spelled correctly
- Check that you have access to the requested model
- Some models may be in preview and require special access

**Quota Exceeded**
```
Error: Quota exceeded
```
- Check your daily/monthly quota limits
- Wait for the quota to reset
- Upgrade your plan for higher limits
