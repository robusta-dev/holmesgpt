# Signup Service Debugging Runbook

## Overview
When the signup service is experiencing issues, the problem is often related to the payments service dependency. This runbook provides systematic debugging steps.

## Step 1: Check Signup Service Status
```bash
kubectl get pods -l app=signup-service
kubectl describe pod <signup-pod-name>
kubectl logs <signup-pod-name>
```

Look for:
- Pod status and restart count
- Error messages in logs
- Connection timeouts to payments service

## Step 2: Verify Payments Service Health
**CRITICAL**: Always check the payments service first when signup issues occur.

```bash
kubectl get pods -l app=payments-service
kubectl describe pod <payments-pod-name>
kubectl logs <payments-pod-name>
```

Common payments service issues that affect signup:
- Invalid Stripe API key causing authentication failures
- Database connection issues in payments service
- Payments service not responding to health checks
- Resource constraints causing payments service to be unstable

## Step 3: Test Service-to-Service Communication
```bash
# Test if signup can reach payments service
kubectl exec -it <signup-pod-name> -- curl -v http://payments-service:8080/health

# Check if payments service is responding
kubectl port-forward svc/payments-service 8080:8080
curl http://localhost:8080/health
```

## Step 4: Check Payments Service Specific Issues

### Stripe API Key Issues
```bash
kubectl logs <payments-pod-name> | grep -i stripe
kubectl logs <payments-pod-name> | grep -i "api key"
```

Look for:
- "Invalid API key" errors
- "Authentication failed" messages
- Stripe connection timeouts

### Database Connection Issues
```bash
kubectl logs <payments-pod-name> | grep -i database
kubectl logs <payments-pod-name> | grep -i postgres
```

## Step 5: Verify Environment Variables
```bash
kubectl exec <payments-pod-name> -- env | grep STRIPE
kubectl exec <payments-pod-name> -- env | grep DATABASE
```

## Common Root Causes
1. **Invalid Stripe API Key**: Payments service fails to initialize, causing signup to fail
2. **Payments Service Crashlooping**: Due to database connectivity or API key issues
3. **Network Issues**: Service-to-service communication problems
4. **Resource Constraints**: Payments service running out of memory/CPU

## Resolution Steps
1. **Fix Stripe API Key**: Update the STRIPE_API_KEY environment variable
2. **Restart Payments Service**: `kubectl rollout restart deployment/payments-service`
3. **Check Database**: Ensure PostgreSQL is accessible from payments service
4. **Scale Payments Service**: If resource constrained, increase replicas or resources

## Prevention
- Monitor payments service health independently
- Set up alerts for payments service failures
- Use proper health checks and circuit breakers
- Implement retry logic in signup service for payments calls
