# Kubernetes Replica Mismatch Troubleshooting Runbook

## Initial Assessment

1. **Quick diagnosis - check deployment and recent pod events**
   ```bash
   # Get deployment status and recent deployment events
   kubectl describe deployment <deployment-name> -n <namespace> | tail -20

   # Get events for specific pods (more targeted)
   kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>

   # Or get events for all pods of a deployment
   kubectl get pods -n <namespace> -l app=<app-label> -o name | xargs -I {} kubectl get events -n <namespace> --field-selector involvedObject.name={} --sort-by='.lastTimestamp' | tail -20
   ```
   - Deployment describe shows rollout issues but not pod-level problems
   - Pod-specific events reveal the actual failures
   - In large namespaces, filter by pod or label selector

2. **Check deployment status and replica counts**
   ```bash
   kubectl get deployments -n <namespace>
   kubectl get rs -n <namespace> -l app=<app-name>
   kubectl get pods -n <namespace> -l app=<app-name> -o wide
   kubectl get hpa -n <namespace>  # Check if HPA is scaling pods
   ```
   - Compare desired vs current vs ready replicas
   - Note any pods not in Running state
   - Check if HPA is actively scaling
   - Verify deployment wasn't manually scaled to 0

3. **Identify problematic pods**
   ```bash
   kubectl get pods -n <namespace> -l app=<app-name> -o wide
   ```
   - Look for states: CrashLoopBackOff, ImagePullBackOff, Error, Pending, Terminating, Init:0/1
   - Note if all replicas affected or just some

4. **Check cluster resources**
   ```bash
   kubectl top nodes
   kubectl describe nodes | grep -A5 "Allocated resources"
   ```
   - Ensure cluster has capacity for the replicas
   - Check for memory pressure or disk pressure

## Root Cause Analysis

### Step 1: Examine pod states and events

**For CrashLoopBackOff:**
```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
```

**For ImagePullBackOff:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Events:"
kubectl get pod <pod-name> -n <namespace> -o yaml | grep -A5 "image:"
```

**For Failed Probes:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Liveness\|Readiness"
kubectl logs <pod-name> -n <namespace> | tail -50
```

**For Init Container Failures:**
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A20 "Init Containers"
kubectl logs <pod-name> -n <namespace> -c <init-container-name>
```

### Step 2: Check for common blockers

**ConfigMaps and Secrets:**
```bash
kubectl get configmap,secret -n <namespace>
kubectl describe deployment <name> -n <namespace> | grep -A10 "Volumes\|Mounts"
```

**Resource constraints:**
```bash
kubectl top pods -n <namespace>
kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Limits\|Requests"
```

**Service mesh/sidecar issues:**
```bash
kubectl get namespace <namespace> -o yaml | grep "istio-injection"
kubectl get pod <pod-name> -n <namespace> -o yaml | grep -c "sidecar"
```

**PodDisruptionBudgets:**
```bash
kubectl get pdb -n <namespace>
kubectl describe pdb <pdb-name> -n <namespace>
```

### Step 3: Check deployment rollout status

```bash
kubectl rollout status deployment <name> -n <namespace>
kubectl rollout history deployment <name> -n <namespace>
kubectl get replicasets -n <namespace> -l app=<app-name>
```

## Output Formatting Guidelines

### Structure:
```
**Summary: <Service> <status> - <ready>/<desired> replicas running**

**Namespace:** <namespace>
**Status:** <Details about failing replicas and duration>
**Root cause:** <One-line description>
- <Specific detail about the failure>
- <Error message or missing resource>
- <Impact or consequence>

**Possible remediations:**
1. <Most direct fix>
2. <Alternative approach>
3. <Longer-term solution>
```

### Formatting Rules:

1. **Summary line:** Always show ready/desired replica count
2. **Status:** Include specific pod states (CrashLoopBackOff, ImagePullBackOff, etc.)
3. **Root cause:** Start with the immediate cause, then provide context
4. **Remediations:** Order by likelihood of success and ease of implementation

### Common Root Cause Patterns:

- **Configuration issues:** Missing ConfigMap/Secret, bad environment variables
- **Image problems:** Wrong tag, no pull secrets, registry down
- **Resource limits:** OOMKilled, CPU throttling
- **Probe failures:** Slow startup, dependencies not ready
- **Service mesh:** Missing sidecar injection, mTLS issues
- **Rollout problems:** PDB conflicts, deployment strategy issues

## Decision Tree for Remediation

1. **Is it a configuration issue?** → Fix or create missing resources
2. **Is it an image problem?** → Fix registry access or rollback image
3. **Are pods being killed?** → Adjust resource limits or fix memory leaks
4. **Are health checks failing?** → Fix application or adjust probe settings
5. **Is it a rollout issue?** → Complete, pause, or rollback deployment

## Special Considerations

- **Partial failures:** When only some replicas fail, check for node-specific issues
- **Cascade failures:** One failing component may cause others to fail
- **Time-based issues:** Some failures only occur under load or at specific times

---

## Example Replica Mismatch Scenarios

### Example 1: Missing ConfigMap

**Summary: Web frontend service degraded - only 2/5 replicas running**

**Namespace:** production
**Status:** 3 replicas in CrashLoopBackOff for 8+ minutes
**Root cause:** ConfigMap mount missing
- Deployment expects ConfigMap `frontend-config`
- ConfigMap not found in namespace
- Pods failing immediately on startup with "CreateContainerConfigError"

**Possible remediations:**
1. Create missing ConfigMap: `kubectl create configmap frontend-config --from-literal=key=value -n production`
2. Check what config the deployment expects: `kubectl get deployment frontend -n production -o yaml | grep -A10 configMap`
3. If ConfigMap not needed, edit deployment to remove the volume mount: `kubectl edit deployment frontend -n production`

---

### Example 2: Image Pull Failure

**Summary: API service partially down - 1/3 replicas running**

**Namespace:** backend
**Status:** 2 replicas ImagePullBackOff for 15+ minutes
**Root cause:** Image not accessible
- Image: `private-registry.company.com/api-server:v2.1.0`
- Error: "pull access denied, repository does not exist or may require authentication"
- ImagePullSecrets not configured in deployment

**Possible remediations:**
1. Add image pull secret to deployment: `kubectl patch deployment api-server -n backend -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"registry-secret"}]}}}}'`
2. Verify image exists: `docker pull private-registry.company.com/api-server:v2.1.0`
3. Use previous working image tag: `kubectl set image deployment/api-server api-server=private-registry.company.com/api-server:v2.0.9 -n backend`

---

### Example 3: Readiness Probe Failures

**Summary: Database connection pool exhausted - 0/3 replicas healthy**

**Namespace:** services
**Status:** All 3 replicas failing readiness probes for 5+ minutes
**Root cause:** Database connection limit reached
- Readiness probe: HTTP /health returns 503
- Logs show: "connection pool exhausted, max_connections=100 reached"
- Database unable to accept new connections

**Possible remediations:**
1. Increase database connection limit (if possible)
2. Reduce connection pool size per pod: Set env var `DB_POOL_SIZE=20` (currently 40)
3. Check for connection leaks: Review logs for unclosed connections
4. Scale down temporarily: `kubectl scale deployment connection-pool -n services --replicas=2`

---

### Example 4: OOMKilled Pods

**Summary: Memory-intensive batch job failing - 0/4 replicas stable**

**Namespace:** data-processing
**Status:** All 4 replicas OOMKilled repeatedly for 12+ minutes
**Root cause:** Memory limits too low
- Container memory limit: 2Gi
- Pods consistently using >2Gi before being killed
- Exit code 137 (SIGKILL due to OOM)

**Possible remediations:**
1. Increase memory limits: `kubectl patch deployment batch-processor -n data-processing --type='json' -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "4Gi"}]'`
2. Enable vertical pod autoscaling to find optimal resources
3. Optimize application memory usage (requires code changes)
4. Process smaller batches to reduce memory footprint

---

### Example 5: Service Mesh Sidecar Issues

**Summary: Service mesh sidecar injection failing - 3/3 replicas unhealthy**

**Namespace:** microservices
**Status:** All replicas have missing Istio sidecar for 6+ minutes
**Root cause:** Namespace missing sidecar injection label
- Deployment restarted but sidecars not injected
- Namespace missing label: `istio-injection=enabled`
- Service mesh traffic policies blocking non-mesh traffic

**Possible remediations:**
1. Enable injection for namespace: `kubectl label namespace microservices istio-injection=enabled`
2. Restart deployment to trigger injection: `kubectl rollout restart deployment -n microservices`
3. Temporarily allow non-mesh traffic while fixing

---

### Example 6: Service Mesh Webhook Not Working

**Summary: Payment service broken - 0/2 replicas starting**

**Namespace:** payments
**Status:** All replicas stuck in Init:0/1 for 10+ minutes
**Root cause:** Istio sidecar injection webhook failing
- Namespace has `istio-injection=enabled` label
- Webhook configuration exists but not responding
- Init container `istio-init` timing out

**Possible remediations:**
1. Check Istio webhook health: `kubectl get validatingwebhookconfigurations istio-validator-istio-system -o yaml`
2. Restart Istio components: `kubectl rollout restart deployment/istiod -n istio-system`
3. Manually inject sidecar as workaround: `istioctl kube-inject -f deployment.yaml | kubectl apply -f -`
4. Disable injection temporarily: `kubectl label namespace payments istio-injection-`

---

### Example 7: Stuck Rolling Update

**Summary: Rolling update stuck - 2/5 replicas on new version**

**Namespace:** frontend
**Status:** Deployment paused mid-rollout for 10+ minutes
**Root cause:** PodDisruptionBudget blocking update
- PDB allows minimum 4 available pods
- Only 3 pods currently ready (2 old version, 1 new version)
- New pod failing startup probe, preventing progress
- MaxUnavailable=1 means rollout cannot proceed

**Possible remediations:**
1. Check version distribution: `kubectl get pods -n frontend -l app=webapp -L version`
2. Fix failing pod (check logs): `kubectl logs -n frontend -l app=webapp,version=v2.0 --previous`
3. Temporarily reduce PDB minimum: `kubectl patch pdb webapp-pdb -n frontend --type='merge' -p '{"spec":{"minAvailable":2}}'`
4. Rollback if new version broken: `kubectl rollout undo deployment webapp -n frontend`

---

### Example 8: Liveness Probe Too Aggressive

**Summary: API service flapping - 2/3 replicas constantly restarting**

**Namespace:** api
**Status:** Pods killed by liveness probe every 2-3 minutes
**Root cause:** Liveness probe timeout too short
- Application takes 45 seconds to warm up cache
- Liveness probe timeout: 10 seconds, initialDelaySeconds: 30 seconds
- Pods marked unhealthy during normal operation and restarted

**Possible remediations:**
1. Increase probe delays: `kubectl patch deployment api-server -n api --type='json' -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds", "value": 60}]'`
2. Add startup probe for slow starting apps (K8s 1.20+)
3. Optimize application startup time
4. Temporarily disable probe while debugging: `kubectl set probe deployment api-server -n api --liveness --remove`

---

### Example 9: Init Container Database Migration Failing

**Summary: User service upgrade blocked - 0/4 replicas starting**

**Namespace:** users
**Status:** All replicas stuck in Init:0/1 for 15+ minutes
**Root cause:** Database migration init container failing
- Init container `db-migrate` exiting with code 1
- Migration script cannot connect to database
- Main containers never start due to init failure

**Possible remediations:**
1. Check init container logs: `kubectl logs -n users <pod-name> -c db-migrate`
2. Verify database connectivity from pod: `kubectl run -it --rm debug --image=postgres:13 --restart=Never -n users -- psql -h <db-host> -U <user>`
3. Skip migration if already applied: Set env var `SKIP_MIGRATION=true` in init container
4. Rollback to previous version if migration is broken: `kubectl rollout undo deployment user-service -n users`
