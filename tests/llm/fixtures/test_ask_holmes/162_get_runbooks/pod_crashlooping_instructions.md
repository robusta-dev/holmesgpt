# Pod Crashlooping Debugging Runbook

## Overview
This runbook provides step-by-step instructions for debugging pods that are crashlooping (continuously crashing and restarting).

## Step 1: Check Pod Status
```bash
kubectl get pods -n <namespace>
kubectl describe pod <pod-name> -n <namespace>
```

Look for:
- Restart count
- Current status (CrashLoopBackOff, Error, etc.)
- Events section for error messages

## Step 2: Check Pod Logs
```bash
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous  # Previous container logs
```

Common issues to look for:
- Application startup errors
- Configuration file issues
- Database connection failures
- Missing environment variables

## Step 3: Check Resource Constraints
```bash
kubectl top pod <pod-name> -n <namespace>
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 -B 5 "Limits\|Requests"
```

Check for:
- Memory limits too low
- CPU limits too restrictive
- Resource quotas exceeded

## Step 4: Check Configuration
```bash
kubectl get pod <pod-name> -n <namespace> -o yaml
```

Verify:
- Environment variables are set correctly
- Volume mounts are working
- ConfigMaps and Secrets are properly referenced

## Step 5: Check Dependencies
- Database connectivity
- External service availability
- Network policies blocking traffic
- Service account permissions

## Common Solutions
1. **Memory Issues**: Increase memory limits or fix memory leaks
2. **Configuration Issues**: Fix environment variables or config files
3. **Dependency Issues**: Ensure external services are available
4. **Image Issues**: Check if container image is correct and accessible

## Prevention
- Set appropriate resource requests and limits
- Use health checks (liveness and readiness probes)
- Implement proper error handling in applications
- Monitor resource usage and set up alerts
