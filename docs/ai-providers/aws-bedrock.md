# AWS Bedrock

Configure HolmesGPT to use AWS Bedrock foundation models.


## Configuration

### Required Environment Variables

```bash
export AWS_REGION_NAME="us-east-1"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

### Using AWS CLI Configuration

If AWS CLI is configured, find parameters with:

```bash
cat ~/.aws/credentials ~/.aws/config
```

### Using IAM Roles (EC2/ECS)

For AWS services, set only the region:

```bash
export AWS_REGION_NAME="us-east-1"
```

## Usage

```bash
holmes ask "what pods are unhealthy and why?" --model=bedrock/<MODEL_NAME>
```

## Available Models

### Anthropic Claude Models

```bash
# Claude 3.5 Sonnet
holmes ask "analyze deployment failure" --model=bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0

# Claude 3 Opus
holmes ask "complex multi-service issue" --model=bedrock/anthropic.claude-3-opus-20240229-v1:0

# Claude 3 Haiku
holmes ask "quick status check" --model=bedrock/anthropic.claude-3-haiku-20240307-v1:0
```

### Amazon Titan Models

```bash
# Titan Text
holmes ask "cluster summary" --model=bedrock/amazon.titan-text-express-v1
```

### Checking Available Models

List models your account can access:

```bash
aws bedrock list-foundation-models --region=us-east-1
```

!!! note "Regional Availability"
    Different models are available in different AWS regions:

    - **Claude Opus**: Only available in `us-west-2`
    - **Claude Sonnet**: Available in `us-east-1`, `us-west-2`, `eu-west-1`
    - **Claude Haiku**: Available in most regions

## Model Access

Some models require additional approval:

1. Go to AWS Bedrock console
2. Navigate to "Model access"
3. Request access to the models you want to use
4. Wait for approval (usually instant for most models)

## Troubleshooting

**Model Access Denied**
```
Error: Model access denied
```
- Request access to the model in the Bedrock console
- Wait for approval
- Verify you're using the correct model identifier

**Region Errors**
```
Error: Model not available in region
```
- Check if the model is available in your selected region
- Switch to a supported region
- Use `aws bedrock list-foundation-models` to check availability

**Authentication Issues**
```
Error: AWS credentials not found
```
- Verify your AWS credentials are configured
- Check environment variables are set correctly
- Ensure IAM permissions include `bedrock:InvokeModel`

**Throttling**
```
Error: Rate limit exceeded
```
- Bedrock has built-in rate limiting
- Wait and retry
- Consider provisioned throughput for high-volume use cases
