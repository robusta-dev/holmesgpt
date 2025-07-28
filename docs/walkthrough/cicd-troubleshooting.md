# CI/CD Pipeline Troubleshooting

HolmesGPT can be integrated into CI/CD pipelines to automatically troubleshoot deployment failures, providing instant insights when deployments fail.

## Automated Deployment Troubleshooting

Example of using HolmesGPT in a CI/CD pipeline to automatically troubleshoot deployment failures:

```yaml
# .github/workflows/deploy.yml or gitlab-ci.yml
deploy:
  script:
    - |
      # Apply Kubernetes manifests
      kubectl apply -f k8s/

      # Wait for rollout
      if ! kubectl rollout status deployment/app -n production --timeout=300s; then
        echo "Deployment failed - starting HolmesGPT investigation"

        # Capture current state
        kubectl get all -n production > deployment-state.txt
        kubectl describe deployment app -n production >> deployment-state.txt
        kubectl get events -n production --sort-by='.lastTimestamp' | tail -20 >> deployment-state.txt

        # Run HolmesGPT investigation and send directly to Slack
        cat deployment-state.txt | holmes ask \
          "🚨 Deployment Failed in ${CI_PROJECT_NAME}\n\nEnvironment: Production\nCommit: ${CI_COMMIT_SHA}\nPipeline: ${CI_PIPELINE_URL}\n\nThe deployment failed. Analyze why the pods are not becoming ready. Focus on: image pulls, resource limits, probes, and configuration issues" \
          --no-interactive \
          --destination slack \
          --slack-token "$SLACK_TOKEN" \
          --slack-channel "#deployments"

        exit 1
      fi
```

## Simplified Approaches

The built-in Slack integration will automatically format and send the analysis to your specified channel. You can also use a simpler approach for basic deployments:

```bash
# Simple deployment check with Slack notification
kubectl rollout status deployment/app -n prod --timeout=300s || \
  holmes ask "deployment/app in prod namespace failed to roll out" \
    --destination slack \
    --slack-token "$SLACK_TOKEN" \
    --slack-channel "#alerts"
```

## Key Benefits

- **Immediate Diagnosis**: Get instant analysis when deployments fail
- **Context-Aware**: Includes commit SHA, pipeline URL, and environment details
- **Team Notification**: Automatically sends results to team channels
- **Actionable Insights**: Focuses on common deployment issues like image pulls, resource limits, and probe failures

## Configuration Tips

- Set up appropriate Slack tokens and channels for different environments
- Customize the investigation prompt based on your specific deployment patterns
- Consider timeout values appropriate for your deployment complexity
- Include relevant context like commit information and pipeline details
