# Gemini

Configure HolmesGPT to use Google's Gemini models via Google AI Studio.

## Setup

Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey){:target="_blank"}.

## Configuration

```bash
export GEMINI_API_KEY="your-gemini-api-key"
holmes ask "what pods are failing?" --model="gemini/<your-gemini-model>"
```

## Using CLI Parameters

You can also pass the API key directly as a command-line parameter:

```bash
holmes ask "what pods are failing?" --model="gemini/<your-gemini-model>" --api-key="your-api-key"
```

## Additional Resources

HolmesGPT uses the LiteLLM API to support Gemini provider. Refer to [LiteLLM Gemini docs](https://litellm.vercel.app/docs/providers/gemini){:target="_blank"} for more details.
