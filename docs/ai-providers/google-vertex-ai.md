# Google Vertex AI

Configure HolmesGPT to use Google Vertex AI with Gemini models.

## Setup

1. Create a Google Cloud project with Vertex AI API enabled
2. Create a service account with `Vertex AI User` role
3. Download the JSON key file

## Configuration

### Required Environment Variables

```bash
export VERTEXAI_PROJECT="your-project-id"
export VERTEXAI_LOCATION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service_account_key.json"
```

## Usage

```bash
holmes ask "what pods are unhealthy and why?" --model="vertex_ai/<MODEL_NAME>"
```

## Available Models

```bash
# Gemini Pro
holmes ask "analyze deployment issues" --model="vertex_ai/gemini-pro"

# Gemini 2.0 Flash Experimental
holmes ask "complex troubleshooting" --model="vertex_ai/gemini-2.0-flash-exp"

# Gemini 1.5 Flash
holmes ask "quick cluster check" --model="vertex_ai/gemini-1.5-flash"
```

## Authentication Methods

### Service Account (Recommended)

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Application Default Credentials

For Google Cloud environments:

```bash
gcloud auth application-default login
```

### Workload Identity (GKE)

Configure workload identity in your deployment:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  annotations:
    iam.gke.io/gcp-service-account: holmes@project.iam.gserviceaccount.com
```

!!! note "Regional Availability"
    Vertex AI Gemini models are available in specific regions:

    - **us-central1** - Primary region with all models
    - **us-east1** - Secondary region
    - **europe-west1** - European region
    - **asia-southeast1** - Asia-Pacific region

## Troubleshooting

**Authentication Errors**
```
Error: Could not automatically determine credentials
```
- Verify `GOOGLE_APPLICATION_CREDENTIALS` points to valid JSON key
- Check that the service account has necessary permissions
- Ensure the Vertex AI API is enabled in your project

**Project Configuration**
```
Error: Project not found or access denied
```
- Verify `VERTEXAI_PROJECT` is set to the correct project ID
- Check that Vertex AI API is enabled
- Ensure billing is enabled for the project

**Regional Issues**
```
Error: Model not available in region
```
- Some models are only available in specific regions
- Try switching to `us-central1` or another supported region

**Permission Errors**
```
Error: Permission denied
```
- Ensure service account has `Vertex AI User` role
- Check that the account has access to the specific model
- Verify project permissions and billing status

**Quota Exceeded**
```
Error: Quota exceeded
```
- Check your quota limits in Google Cloud Console
- Request quota increases if needed
