# Kubectl Run Image Toolset

The kubectl run image toolset provides secure execution of temporary containers in Kubernetes clusters for diagnostic and troubleshooting purposes. It creates temporary debug pods that are automatically cleaned up after execution.

**⚠️ Security Note**: This toolset can create pods in your Kubernetes cluster. It requires careful configuration with whitelisted images and command patterns to ensure security.

## Overview

This toolset uses `kubectl run` to create temporary containers that:

- Execute diagnostic commands in specified container images
- Automatically clean up pods after execution (using `--rm` flag)
- Support custom namespaces and timeouts
- Provide isolated environments for network debugging, DNS resolution, and environment inspection

## Use Cases

- **Network Debugging**: Test connectivity between services using network utilities
- **DNS Resolution**: Verify DNS configuration and resolution from within the cluster  
- **Environment Inspection**: Check environment variables, file systems, and configuration
- **Service Testing**: Test HTTP endpoints, database connections, or API calls
- **Resource Analysis**: Examine cluster resources from a pod's perspective

## Configuration

The toolset requires explicit configuration of allowed images and command patterns for security:

=== "YAML"

    ```yaml
    toolsets:
      kubectl_run_image:
        enabled: true
        config:
          allowed_images:
            - image: "busybox"
              allowed_commands:
                - "nslookup .*"
                - "cat /etc/resolv.conf"
                - "echo .*"
            - image: "curlimages/curl"
              allowed_commands:
                - "curl -s http://.*"
                - "curl -I .*"
            - image: "registry.k8s.io/e2e-test-images/jessie-dnsutils:1.3"
              allowed_commands:
                - "nslookup .*"
                - "dig .*"
                - "host .*"
    ```

=== "Python"

    ```python
    from holmes import Config

    config = Config(
        toolsets={
            "kubectl_run_image": {
                "enabled": True,
                "config": {
                    "allowed_images": [
                        {
                            "image": "busybox",
                            "allowed_commands": [
                                "nslookup .*",
                                "cat /etc/resolv.conf",
                                "echo .*"
                            ]
                        },
                        {
                            "image": "curlimages/curl", 
                            "allowed_commands": [
                                "curl -s http://.*",
                                "curl -I .*"
                            ]
                        }
                    ]
                }
            }
        }
    )
    ```

## Configuration Options

### `allowed_images`
List of image configurations that define which container images can be used.

**Required**: Yes

### Image Configuration

Each image entry supports:

- **`image`** (string, required): The container image name
- **`allowed_commands`** (list, required): Regular expression patterns for allowed commands

### Command Pattern Matching

Commands are validated against regex patterns:

- `"echo .*"` - Allows any echo command
- `"curl -s http://.*"` - Allows curl with -s flag to HTTP URLs  
- `"nslookup [a-zA-Z0-9.-]+"` - Allows nslookup with domain names
- `"cat /etc/resolv.conf"` - Allows reading the DNS resolver configuration

## Tool Parameters

### `kubectl_run_image`

Creates and runs a temporary pod with the specified image and command.

**Parameters:**

- **`image`** (string, required): Container image to run (must be in allowed list)
- **`command`** (string, required): Command to execute (must match allowed patterns)  
- **`namespace`** (string, optional): Kubernetes namespace (defaults to "default")
- **`timeout`** (integer, optional): Command timeout in seconds (defaults to 60)

## Example Usage

### Network Connectivity Test

```bash
# Test connectivity to a service
kubectl_run_image(
    image="curlimages/curl",
    command="curl -s http://my-service:8080/health",
    namespace="production"
)
```

### DNS Resolution Check

```bash
# Check DNS resolution
kubectl_run_image(
    image="busybox", 
    command="nslookup my-service.production.svc.cluster.local",
    namespace="production"
)
```

### Environment Inspection

```bash
# Check environment variables
kubectl_run_image(
    image="busybox",
    command="echo $KUBERNETES_SERVICE_HOST",
    namespace="default"
)
```

## Security Considerations

### Image Whitelisting

- Only pre-approved container images can be used
- Images should be from trusted registries
- Consider using specific image tags rather than `latest`

### Command Validation  

- All commands are validated against regex patterns
- Dangerous commands (file writes, network changes) should not be allowed
- Use restrictive patterns that only allow necessary operations

### Namespace Restrictions

- The toolset validates namespace names for safety
- Namespaces must match safe naming patterns
- Consider restricting to specific namespaces in production

### Resource Management

- Pods are automatically cleaned up using `--rm` flag
- Set appropriate timeouts to prevent hanging pods
- Monitor resource usage and set limits if needed

## Common Image Recommendations

### Network Debugging
- `busybox` - Basic utilities including nslookup, ping, telnet
- `curlimages/curl` - HTTP testing and API calls  
- `registry.k8s.io/e2e-test-images/jessie-dnsutils:1.3` - DNS utilities

### Database Testing
- `postgres:alpine` - PostgreSQL client tools
- `mysql:8.0` - MySQL client tools
- `redis:alpine` - Redis client tools

### Security Scanning
- `aquasec/trivy` - Vulnerability scanning
- `clair-scanner` - Container security scanning

## Troubleshooting

### Permission Issues

Ensure the Holmes service account has the necessary RBAC permissions:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: holmes-kubectl-run
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["create", "get", "list", "delete"]
```

### Image Pull Errors

- Verify images exist and are accessible from the cluster
- Check image registry authentication if using private images
- Ensure image names include full registry paths when needed

### Command Validation Failures

- Check that commands match the configured regex patterns exactly
- Test regex patterns separately to ensure they work as expected
- Remember that patterns are matched against the entire command string