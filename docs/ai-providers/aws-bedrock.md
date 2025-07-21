# AWS Bedrock

Configure HolmesGPT to use AWS Bedrock foundation models.

## Setup

### Prerequisites

1. **Install boto3**: AWS Bedrock requires boto3 version 1.28.57 or higher:
   ```bash
   pip install "boto3>=1.28.57"
   ```

2. **AWS credentials**: Ensure you have AWS credentials configured with access to Bedrock models. See [AWS Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html){:target="_blank"}.

## Configuration

### Environment Variables

```bash
export AWS_REGION_NAME="us-east-1"  # Replace with your region
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

holmes ask "what pods are failing?" --model="bedrock/<your-bedrock-model>"
```

### Finding Your AWS Credentials

If the AWS CLI is already configured on your machine, you may be able to find the above values with:

```bash
cat ~/.aws/credentials ~/.aws/config
```

### Finding Available Models

To list models your account can access (replacing `us-east-1` with the relevant region):

```bash
aws bedrock list-foundation-models --region=us-east-1 | grep modelId
```

**Important**: Different models are available in different regions. For example, Claude Opus is only available in us-west-2.

### Model Name Examples

Be sure to replace `<your-bedrock-model>` with a model you have access to, such as `anthropic.claude-3-5-sonnet-20240620-v1:0`

## Additional Resources

HolmesGPT uses the LiteLLM API to support AWS Bedrock provider. Refer to [LiteLLM Bedrock docs](https://litellm.vercel.app/docs/providers/bedrock){:target="_blank"} for more details.
