# Kubernetes Troubleshooting Scenarios (76-85)

## Overview
Successfully implemented 10 typical Kubernetes troubleshooting scenarios that developers and SREs commonly encounter. Each scenario is isolated in its own namespace and designed to not impact cluster operations.

## Implementation Summary

| Eval | Scenario | Root Cause | Key Symptoms |
|------|----------|------------|--------------|
| 76 | Service Discovery Issue | Service selector mismatch | Frontend can't connect to backend, no endpoints |
| 77 | Liveness Probe Misconfiguration | Probe on wrong port (8080 vs 80) | Pod keeps restarting |
| 78 | Resource Quota Exceeded | Namespace quota too low | Pods stuck in Pending state |
| 79 | ConfigMap Mount Issue | ConfigMap doesn't exist | Pod stuck in ContainerCreating |
| 80 | PVC Storage Class Mismatch | Storage class doesn't exist | PVC won't bind |
| 81 | Service Account Permission Denied | Missing RBAC verb | 403 Forbidden errors |
| 82 | Pod Anti-Affinity Conflict | Strict anti-affinity rules | Pods can't be scheduled |
| 83 | Secret Not Found | Secret name mismatch | Pod fails to start |
| 84 | Network Policy Blocking Traffic | Restrictive ingress rules | Connection timeouts |
| 85 | HPA Not Scaling | Missing resource requests | HPA can't calculate metrics |

## Key Features

### Isolation
- Each scenario in its own namespace (namespace-76 through namespace-85)
- No cluster-wide resources used
- Clean removal with namespace deletion
- Resource limits: 50-200m CPU, 64-256Mi memory per pod

### Realism
- Common misconfigurations developers make
- Clear error messages in events/logs
- Realistic service interactions
- Typical troubleshooting patterns

### Testing

## Running the Tests

To run all Kubernetes scenarios:
```bash
poetry run pytest tests/llm/test_ask_holmes.py -k "76_|77_|78_|79_|80_|81_|82_|83_|84_|85_" -v
```

To run a specific scenario:
```bash
poetry run pytest "tests/llm/test_ask_holmes.py::test_ask_holmes[76_service_discovery_issue]" -v
```

## Common Troubleshooting Patterns

1. **Service Discovery** (76): Check service selectors match pod labels
2. **Pod Restarts** (77): Examine liveness/readiness probes
3. **Pending Pods** (78, 82): Check resource quotas and scheduling constraints
4. **ContainerCreating** (79, 83): Verify volumes and mounts exist
5. **PVC Issues** (80): Check storage classes and provisioners
6. **Permission Errors** (81): Review RBAC roles and bindings
7. **Network Issues** (84): Check NetworkPolicies and connectivity
8. **Scaling Issues** (85): Verify resource requests for HPA

## Expected Behaviors

Holmes should:
1. Identify the misconfiguration quickly
2. Provide the specific cause (e.g., "selector mismatch", "missing verb")
3. Suggest the fix or point to the exact issue
4. Use appropriate Kubernetes commands (describe, get, logs)

## Notes

- All scenarios use minimal resources to avoid cluster impact
- Setup time is 20-45 seconds depending on the scenario
- Some scenarios (like 77) need extra time for symptoms to appear
- Network policies (84) require CNI support for enforcement
- HPA (85) requires metrics-server to be installed
