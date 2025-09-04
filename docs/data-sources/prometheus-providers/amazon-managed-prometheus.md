# Amazon Managed Prometheus (AMP)

Configure HolmesGPT to use Amazon Managed Prometheus for metrics analysis in AWS environments.

## Prerequisites

- AWS account with AMP workspace
- IAM credentials or IRSA (IAM Roles for Service Accounts) configured
- AMP workspace endpoint URL

## Configuration Options

### Option 1: Using IRSA (Recommended for EKS)

If running HolmesGPT in EKS with IRSA configured:

```yaml-toolset-config
toolsets:
  prometheus/metrics:
    enabled: true
    config:
      prometheus_url: "https://aps-workspaces.us-west-2.amazonaws.com/workspaces/ws-xxxxx"
      aws_region: "us-west-2"
      # IRSA credentials will be automatically detected
```

### Option 2: Using IAM Credentials

```yaml-toolset-config
toolsets:
  prometheus/metrics:
    enabled: true
    config:
      prometheus_url: "https://aps-workspaces.us-west-2.amazonaws.com/workspaces/ws-xxxxx"
      aws_region: "us-west-2"
      aws_access_key: "YOUR_ACCESS_KEY"  # Consider using environment variables
      aws_secret_access_key: "YOUR_SECRET_KEY"  # Consider using environment variables
```

### Option 3: Using Environment Variables (Recommended)

=== "CLI"

    Set AWS credentials as environment variables:
    ```bash
    export AWS_ACCESS_KEY_ID="your-access-key"
    export AWS_SECRET_ACCESS_KEY="your-secret-key"
    export AWS_REGION="us-west-2"
    ```

    Configure `~/.holmes/config.yaml`:
    ```yaml
    toolsets:
      prometheus/metrics:
        enabled: true
        config:
          prometheus_url: "https://aps-workspaces.us-west-2.amazonaws.com/workspaces/ws-xxxxx"
          aws_region: "us-west-2"
    ```

=== "Kubernetes (Helm)"

    Store credentials as a Kubernetes secret:
    ```bash
    kubectl create secret generic aws-credentials \
      --from-literal=AWS_ACCESS_KEY_ID='your-access-key' \
      --from-literal=AWS_SECRET_ACCESS_KEY='your-secret-key'
    ```

    Configure your Helm values:
    ```yaml
    additionalEnvVars:
      - name: AWS_ACCESS_KEY_ID
        valueFrom:
          secretKeyRef:
            name: aws-credentials
            key: AWS_ACCESS_KEY_ID
      - name: AWS_SECRET_ACCESS_KEY
        valueFrom:
          secretKeyRef:
            name: aws-credentials
            key: AWS_SECRET_ACCESS_KEY

    toolsets:
      prometheus/metrics:
        enabled: true
        config:
          prometheus_url: "https://aps-workspaces.us-west-2.amazonaws.com/workspaces/ws-xxxxx"
          aws_region: "us-west-2"
    ```

## Finding Your AMP Workspace URL

1. Navigate to the Amazon Managed Service for Prometheus console
2. Select your workspace
3. Copy the **Workspace endpoint URL**
4. Your URL format should be: `https://aps-workspaces.REGION.amazonaws.com/workspaces/WORKSPACE_ID`

## IAM Permissions Required

Your IAM user or role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "aps:QueryMetrics",
        "aps:GetSeries",
        "aps:GetLabels",
        "aps:GetMetricMetadata"
      ],
      "Resource": "arn:aws:aps:REGION:ACCOUNT:workspace/WORKSPACE_ID"
    }
  ]
}
```

## Configuration Notes

- **Authentication**: AMP uses AWS SigV4 authentication, which is handled automatically
- **SSL**: SSL verification is disabled by default for AMP (set by the AMPConfig class)
- **Healthcheck**: Automatically set to `api/v1/query?query=up` for AMP compatibility
- **IRSA**: If using IRSA, ensure your service account is properly annotated with the IAM role

## Validation

Test your configuration:

```bash
holmes ask "What metrics are available in my AMP workspace?"
```

## Troubleshooting

### Authentication Errors
- Verify IAM permissions are correct
- Check AWS credentials are properly set
- For IRSA, ensure the service account has the correct annotation

### Connection Issues
- Verify the workspace URL is correct
- Check the AWS region matches your workspace location
- Ensure network connectivity from your cluster to AMP

### No Metrics Found
- Confirm metrics are being ingested into AMP
- Check that Prometheus remote write is configured correctly
- Verify the time range of your queries

## Additional Options

For all available Prometheus configuration options, see the [main Prometheus documentation](../prometheus.md#advanced-configuration).
