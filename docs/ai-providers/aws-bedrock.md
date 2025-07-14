# AWS Bedrock

Configure HolmesGPT to use AWS Bedrock foundation models.

## Setup

Ensure you have AWS credentials configured with access to Bedrock models. Set up your [AWS credentials](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html){:target="_blank"}.

## Configuration

```bash
export AWS_REGION_NAME="us-east-1"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

holmes ask "what pods are failing?" --model="bedrock/<your-bedrock-model>"
```

## Using CLI Parameters

You can also pass credentials directly as command-line parameters:

```bash
holmes ask "what pods are failing?" --model="bedrock/<your-bedrock-model>" --api-key="your-aws-access-key"
```

## Additional Resources

HolmesGPT uses the LiteLLM API to support AWS Bedrock provider. Refer to [LiteLLM AWS Bedrock docs](https://litellm.vercel.app/docs/providers/bedrock){:target="_blank"} for more details.
