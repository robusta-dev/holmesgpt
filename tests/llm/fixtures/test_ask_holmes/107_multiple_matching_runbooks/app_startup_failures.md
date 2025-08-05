# Application Startup Failures - Configuration and Dependencies

## Overview
Troubleshooting applications that fail during startup due to configuration issues, missing dependencies, or initialization problems.

## Investigation Steps

### 1. Check Container Start Status
Identify the exact failure point:
```bash
kubectl get pods -n {namespace} -l app={app_name} -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\t"}{.status.containerStatuses[*].state}{"\n"}{end}'
```

### 2. Examine Startup Logs
Look for configuration loading errors:
```bash
kubectl logs -n {namespace} -l app={app_name} --tail=100 | grep -E "(config|Config|FATAL|ERROR|Missing|required)"
```

### 3. Verify ConfigMaps and Secrets
Ensure all configuration resources exist:
```bash
# List all ConfigMaps and Secrets
kubectl get configmaps,secrets -n {namespace}

# Check if referenced configs exist in deployment
kubectl get deployment {app_name} -n {namespace} -o yaml | grep -A5 -E "(configMapRef|secretRef|configMap:|secret:)"
```

### 4. Validate Configuration Content
Check for syntax errors or missing required fields:
```bash
# Examine ConfigMap content
kubectl get configmap {config_name} -n {namespace} -o yaml

# Check environment variables
kubectl describe pod -n {namespace} -l app={app_name} | grep -A20 "Environment:"
```

### 5. Check Init Containers
Verify initialization steps completed:
```bash
kubectl describe pod -n {namespace} -l app={app_name} | grep -A10 "Init Containers:"
```

### 6. Dependency Services
Verify required services are available:
```bash
# Check deployment annotations for dependencies
kubectl get deployment {app_name} -n {namespace} -o jsonpath='{.metadata.annotations}'

# Common dependency checks
kubectl get svc -n {namespace} | grep -E "(database|cache|queue|api)"
```

## Common Startup Failures

1. **Missing Required Configuration**: Required config keys not present in ConfigMap/Secret
2. **Invalid Configuration Format**: YAML/JSON parsing errors, wrong data types
3. **Database Connection String**: Incorrect format or missing credentials
4. **Service Dependencies**: Required services not available at startup
5. **File Permissions**: Config files not readable due to wrong permissions
6. **Environment Specific**: Using production config in development or vice versa
