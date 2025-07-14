# Google Vertex AI

Configure HolmesGPT to use Google Vertex AI with Gemini models.

## Setup

1. Create a Google Cloud project with [Vertex AI API enabled](https://cloud.google.com/vertex-ai/docs/start/introduction-unified-platform){:target="_blank"}
2. Create a service account with `Vertex AI User` role
3. Download the JSON key file

## Configuration

```bash
export VERTEXAI_PROJECT="your-project-id"
export VERTEXAI_LOCATION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"

holmes ask "what pods are failing?" --model="vertex_ai/<your-vertex-model>"
```

## Using CLI Parameters

You can also pass credentials directly as command-line parameters:

```bash
holmes ask "what pods are failing?" --model="vertex_ai/<your-vertex-model>" --api-key="your-service-account-key"
```

## Additional Resources

HolmesGPT uses the LiteLLM API to support Google Vertex AI provider. Refer to [LiteLLM Google Vertex AI docs](https://litellm.vercel.app/docs/providers/vertex){:target="_blank"} for more details.
