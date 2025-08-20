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

## Gemini-Specific Configuration

Gemini models require special handling for tools without parameters. Set the following environment variable when using Gemini:

```bash
export TOOL_SCHEMA_NO_PARAM_OBJECT_IF_NO_PARAMS=true
```

This ensures that tool schemas are formatted correctly for Gemini's requirements. See the [Environment Variables Reference](../reference/environment-variables.md#tool_schema_no_param_object_if_no_params) for more details.

## Additional Resources

HolmesGPT uses the LiteLLM API to support Gemini provider. Refer to [LiteLLM Gemini docs](https://litellm.vercel.app/docs/providers/gemini){:target="_blank"} for more details.
