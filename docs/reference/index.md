# Reference

Complete reference documentation for HolmesGPT configuration, commands, and troubleshooting.

## Reference Documentation

### Configuration Reference
- **[Helm Configuration](helm-configuration.md)** - Complete Helm configuration reference

## Quick Reference

### Essential Commands

```bash
# Install HolmesGPT
helm install holmesgpt robusta/robusta --set enableHolmesGPT=true

# Check status
kubectl get pods -n robusta

# View logs
kubectl logs -n robusta deployment/holmes
```

### Key Configuration Keys

```yaml
# Enable HolmesGPT
enableHolmesGPT: true

# AI Provider (OpenAI example)
holmes:
  additionalEnvVars:
  - name: MODEL
    value: gpt-4o
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: openAiKey
```

### Common Troubleshooting

| Issue | Solution |
|-------|----------|
| AI provider errors | Check API keys and model availability |
| No data sources | Verify toolset configuration and credentials |
| Slow responses | Review model selection and resource limits |
| Permission errors | Check RBAC and secret access |

## Getting Help

Can't find what you're looking for?

1. **Search** this documentation using the search bar
2. **Check** our troubleshooting guide for common issues
3. **Visit** our [troubleshooting guide](troubleshooting.md)
4. **Ask** in our [Slack community](https://robustacommunity.slack.com)
5. **Report** issues on [GitHub](https://github.com/robusta-dev/holmesgpt/issues)

Start with the [troubleshooting guide](troubleshooting.md) for answers to common questions.
