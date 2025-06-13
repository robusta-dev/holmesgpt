# AWS Bedrock

Configure HolmesGPT to use AWS Bedrock foundation models.


## Configuration

### Required Environment Variables

```bash
export AWS_REGION_NAME="us-east-1"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

## Using CLI Arguments

```bash
holmes ask "what pods are unhealthy and why?" --model=bedrock/<MODEL_NAME>
```

## Using Environment Variables

```bash
export MODEL="bedrock/<MODEL_NAME>"
holmes ask "analyze deployment failure"
```

## Examples

```bash
# Claude 3.5 Sonnet
holmes ask "analyze deployment failure" # with MODEL already set

# Claude 3 Opus
holmes ask "complex multi-service issue" --model=bedrock/anthropic.claude-3-opus-20240229-v1:0

# Claude 3 Haiku
holmes ask "quick status check" --model=bedrock/anthropic.claude-3-haiku-20240307-v1:0
```

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
