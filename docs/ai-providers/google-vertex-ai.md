# Google Vertex AI

Configure HolmesGPT to use Google Vertex AI with Gemini models.

## Setup

1. Create a Google Cloud project with Vertex AI API enabled
2. Create a service account with `Vertex AI User` role
3. Download the JSON key file

## Configuration

```bash
export VERTEXAI_PROJECT="your-project-id"
export VERTEXAI_LOCATION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"

holmes ask "what pods are failing?" --model="vertex_ai/<your-vertex-model>"
```
