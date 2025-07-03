# AWS Bedrock

Configure HolmesGPT to use AWS Bedrock foundation models.

## Configuration

```bash
export AWS_REGION_NAME="us-east-1"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

holmes ask "what pods are failing?" --model="bedrock/<your-bedrock-model>"
```
