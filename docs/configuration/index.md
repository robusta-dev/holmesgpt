# Configuration

Advanced configuration options for optimizing HolmesGPT performance, security, and integration with your environment.

## Configuration Areas

### Core Configuration
- **[Helm Configuration](../reference/helm-configuration.md)** - Complete Helm values reference
- **[Security & Permissions](security.md)** - RBAC, secrets, and access control

### Performance & Monitoring
- **[Performance Tuning](performance.md)** - Optimize AI provider usage and response times
- **[Monitoring & Observability](monitoring.md)** - Monitor HolmesGPT itself

### Troubleshooting
- **[Troubleshooting](../reference/troubleshooting.md)** - Common issues and solutions

## Configuration Priority

HolmesGPT configuration follows this hierarchy:

1. **Helm values** - Primary configuration method
2. **Environment variables** - Runtime overrides
3. **ConfigMaps** - Shared configuration
4. **Secrets** - Sensitive data (API keys, tokens)

## Quick Configuration Checklist

Essential settings to configure:

- [ ] **AI Provider** - Choose and configure your preferred AI service
- [ ] **Data Sources** - Enable relevant toolsets for your infrastructure
- [ ] **Security** - Set up proper RBAC and secret management
- [ ] **Monitoring** - Enable observability for HolmesGPT operations

## Advanced Topics

Once you have basic configuration working:

- **Resource limits** - Tune CPU and memory allocation
- **Scaling** - Configure horizontal pod autoscaling
- **Network policies** - Restrict network access
- **Backup & recovery** - Protect configuration and data

## Configuration Examples

Common configuration patterns:

=== "Production Setup"
    - Multiple AI providers for redundancy
    - Comprehensive monitoring
    - Strict security policies
    - Performance optimization

=== "Development Setup"
    - Single AI provider
    - Relaxed security for testing
    - Debug logging enabled
    - Cost optimization

=== "Multi-Tenant Setup"
    - Namespace isolation
    - Per-tenant AI provider configuration
    - Shared monitoring infrastructure

Start with [Helm Configuration](../reference/helm-configuration.md) for the complete configuration reference.
