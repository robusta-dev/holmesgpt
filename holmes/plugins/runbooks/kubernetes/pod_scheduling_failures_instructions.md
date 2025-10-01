---
update_date: 2025-07-24
description: Runbook to diagnose and resolve Kubernetes pod scheduling failures (Pending pods, FailedScheduling events)
---

# Kubernetes Pod Scheduling Failure Runbook

## Initial Assessment

1. **Identify the failing pods**
   ```bash
   kubectl get pods -A | grep -E "(Pending|0/)"
   ```
   - Note the namespace, pod names, and how many replicas are affected
   - Record how long pods have been pending

2. **Get detailed pod information**
   ```bash
   kubectl describe pod <pod-name> -n <namespace>
   ```
   - Focus on the Events section at the bottom
   - Look for `FailedScheduling` events which contain the root cause

## Root Cause Analysis

### Step 1: Parse the FailedScheduling message

Common patterns to identify:

- **"Insufficient cpu/memory"** → Resource exhaustion
- **"didn't match Pod's node affinity/selector"** → Node selector mismatch
- **"didn't tolerate taint"** → Taint/toleration issue
- **"didn't match pod anti-affinity rules"** → Anti-affinity conflict
- **"node(s) had volume node affinity conflict"** → PV zone mismatch
- **"max node group size reached"** → Autoscaling blocked
- **"Insufficient pods"** → PodDisruptionBudget blocking

### Step 2: Gather supporting details

Based on the root cause, collect additional information:

**For resource issues:**
```bash
kubectl top nodes  # Check actual usage
kubectl describe nodes | grep -A5 "Allocated resources"  # Check requests
```

**For node selector issues:**
```bash
kubectl get nodes --show-labels
kubectl get deployment <name> -n <namespace> -o yaml | grep -A5 nodeSelector
```

**For taint issues:**
```bash
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints
```

**For PV issues:**
```bash
kubectl get pv <pv-name> -o wide  # Check zone
kubectl get nodes --label-columns topology.kubernetes.io/zone
```

### Step 3: Identify Cloud Provider and Gather Context

**Detect cloud provider from node labels:**
```bash
kubectl get nodes -o json | jq -r '.items[0].metadata.labels | keys[]' | grep -E "(cloud.google.com|eks.amazonaws.com|kubernetes.azure.com)"
```

Common provider indicators:
- **GKE**: `cloud.google.com/gke-nodepool`, `cloud.google.com/gke-os-distribution`
- **EKS**: `eks.amazonaws.com/nodegroup`, `eks.amazonaws.com/cluster-name`
- **AKS**: `kubernetes.azure.com/cluster`, `agentpool`

**Gather provider-specific information for console links:**

For GKE:
```bash
# Get project ID and cluster name
kubectl get nodes -o json | jq -r '.items[0].metadata.labels["cloud.google.com/gke-nodepool"]'
gcloud config get-value project
gcloud container clusters list --format="value(name,location)"
```

For EKS:
```bash
# Get cluster name and region
kubectl get nodes -o json | jq -r '.items[0].spec.providerID' | cut -d'/' -f4
kubectl get nodes -o json | jq -r '.items[0].metadata.labels["topology.kubernetes.io/region"]'
```

For AKS:
```bash
# Get resource group and cluster name from node resource ID
kubectl get nodes -o json | jq -r '.items[0].spec.providerID' | grep -oP '(?<=resourceGroups/)[^/]+|(?<=managedClusters/)[^/]+'
```

## Output Formatting Guidelines

### Structure:
```
**Summary: <Service> deployment <status> - <X>/<Y> pods unschedulable**

**Namespace:** <namespace>
**Status:** <Details about replicas and duration>
**Root cause:** <One-line description>
- <Specific detail 1>
- <Specific detail 2>
- <Additional context if needed>

**Possible remediations:**
1. <Most likely/easiest fix>
2. <Alternative approach>
3. <Long-term solution>
```

### Formatting Rules:

1. **Summary line:** Always include service type, deployment name if known, and pod count
2. **Status:** Use "All X replicas" or "Y of X replicas" format
3. **Root cause:**
   - Start with clear problem statement
   - Use bullet points for details
   - Include specific numbers (CPU/memory requests, node counts, etc.)
   - For autoscaling issues, always note if it's blocked

4. **Remediations:**
   - Order by practicality (quickest/easiest first)
   - Include kubectl commands where helpful, but keep them concise
   - For GKE-specific solutions, include console links
   - Explain non-obvious impacts (e.g., "allows co-location but prefers separation")

### Cloud Provider Console Link Generation

Only include console links when you have confirmed:
1. The cloud provider (from node labels)
2. Required identifiers (project/account ID, cluster name, region)
3. The link is relevant to the specific remediation

**GKE Console Links:**
- Node pool scaling: `https://console.cloud.google.com/kubernetes/nodepool/[REGION]/[CLUSTER_NAME]/[NODEPOOL_NAME]?project=[PROJECT_ID]`
- Cluster settings: `https://console.cloud.google.com/kubernetes/clusters/details/[REGION]/[CLUSTER_NAME]?project=[PROJECT_ID]`

**EKS Console Links:**
- Node group scaling: `https://console.aws.amazon.com/eks/home?region=[REGION]#/clusters/[CLUSTER_NAME]/nodegroups/[NODEGROUP_NAME]`
- Cluster compute: `https://console.aws.amazon.com/eks/home?region=[REGION]#/clusters/[CLUSTER_NAME]/compute`

**AKS Console Links:**
- Node pool scaling: `https://portal.azure.com/#resource/subscriptions/[SUBSCRIPTION_ID]/resourceGroups/[RESOURCE_GROUP]/providers/Microsoft.ContainerService/managedClusters/[CLUSTER_NAME]/nodePools`

**Link Inclusion Rules:**
- Only include links when you have ALL required parameters
- Use generic text like "[increase node group max size]" if parameters are missing
- Never guess or use placeholder values in URLs

### Style Guidelines:

- Use active voice: "Pod requires" not "Required by pod"
- Be specific with numbers: "4 nodes: Insufficient memory (pods need 64Mi, nodes have <50Mi available)"
- For complex concepts, add one-line explanations: "**Issue:** Pod must run in same zone as its storage volume due to cloud provider limitations"
- Keep remediation descriptions action-oriented: "Reduce memory/CPU requests" not "Consider reducing"

## Decision Tree for Remediation Suggestions

1. **Can the pod requirements be reduced?** → Suggest reducing requests
2. **Can other workloads be optimized?** → Suggest using KRR or similar tools
3. **Can infrastructure be expanded?** → Provide expansion options with links
4. **Does the issue require application changes?** → Note this as the last option

## Special Cases

- **Multiple issues:** If Events show multiple problems, address the most restrictive first
- **Cascade failures:** Check if the scheduling failure is causing other issues
- **Time-sensitive:** For pods pending >10 minutes, emphasize quick fixes over optimal solutions

---

## Example Scheduling Failure Scenarios

### Example 1: Resource Exhaustion

**Summary: Redis cache deployment down - 3/3 pods unschedulable**

**Namespace:** production
**Status:** All 3 cache-server replicas pending for 4+ minutes
**Root cause:** No viable nodes in cluster
- 4 nodes: Insufficient memory (pods need 64Mi, nodes have <50Mi available)
- 1 node: Insufficient CPU (pods need 50m, node has 30m available) + memory pressure
- Autoscaling: Blocked - node group at maximum size

**Possible remediations:**
1. Reduce memory/CPU requests on this deployment to fit available node capacity
2. Free up capacity by right-sizing other workloads - use tools like KRR to find candidates
3. Expand capacity: increase node group max size
   - For GKE: `https://console.cloud.google.com/kubernetes/nodepool` (requires project ID and cluster details)
   - For EKS: Check AWS EKS console in your cluster's region
   - For AKS: Access via Azure portal for your resource group

---

### Example 2: Node Selector Mismatch

**Summary: API service deployment down - 2/2 pods unschedulable**

**Namespace:** backend
**Status:** All 2 api-server replicas pending for 7+ minutes
**Root cause:** Node selector mismatch
- Pod requires: `disktype=ssd`
- Available nodes: 0 of 8 nodes have this label
- All nodes labeled with `disktype=standard` only

**Possible remediations:**
1. Remove disktype selector from deployment if SSD not critical: `kubectl patch deployment api-server -n backend --type='json' -p='[{"op": "remove", "path": "/spec/template/spec/nodeSelector/disktype"}]'`
2. Add required label to suitable nodes: `kubectl label nodes <node-name> disktype=ssd`
3. Provision new node pool with SSD disks and appropriate labels

---

### Example 3: Taint/Toleration Mismatch

**Summary: ML training job stuck - 4/4 pods unschedulable**

**Namespace:** data-science
**Status:** All 4 training-job replicas pending for 12+ minutes
**Root cause:** Taint/toleration mismatch
- All 6 GPU nodes tainted: `nvidia.com/gpu=true:NoSchedule`
- Pods missing required toleration
- CPU nodes cannot satisfy GPU resource request (4 GPUs per pod)

**Possible remediations:**
1. Add toleration to deployment: `kubectl patch deployment training-job -n data-science --type='json' -p='[{"op": "add", "path": "/spec/template/spec/tolerations", "value": [{"key": "nvidia.com/gpu", "operator": "Equal", "value": "true", "effect": "NoSchedule"}]}]'`
2. Remove taint temporarily: `kubectl taint nodes -l node-type=gpu nvidia.com/gpu-`
3. Deploy to CPU nodes if GPU not required (remove GPU resource request)

---

### Example 4: Pod Anti-Affinity Conflict

**Summary: Web frontend deployment down - 5/5 pods unschedulable**

**Namespace:** frontend
**Status:** All 5 nginx replicas pending for 3+ minutes
**Root cause:** Pod anti-affinity conflict
- Pods configured with anti-affinity: no co-location with other nginx pods
- All 10 nodes already running nginx pods from previous deployment
- Strict `requiredDuringSchedulingIgnoredDuringExecution` prevents scheduling

**Possible remediations:**
1. Change to soft anti-affinity (allows co-location but prefers separation) - edit deployment to use `preferredDuringSchedulingIgnoredDuringExecution`
2. Scale down old deployment first: `kubectl scale deploy nginx-old --replicas=0`
3. Remove anti-affinity rules temporarily if high availability less critical than uptime

---

### Example 5: Persistent Volume Zone Mismatch

**Summary: Database deployment down - 1/1 pods unschedulable**

**Namespace:** postgres
**Status:** Primary database pod pending for 15+ minutes
**Root cause:** Persistent volume zone mismatch
- **Issue:** Pod must run in same zone as its storage volume due to cloud provider limitations
- PVC bound to PV in `us-east1-b` (checked: PV exists and is Available)
- No nodes available in `us-east1-b` (all 12 nodes in `us-east1-c` and `us-east1-d`)
- Volume cannot be attached cross-zone

**Possible remediations:**
1. Add nodes to zone `us-east1-b`: create node pool in correct zone
   - For GKE: Access cluster settings in Cloud Console
   - For EKS: Add node group with appropriate subnet in `us-east1-b`
   - For AKS: Scale node pool in the required availability zone
2. Migrate data to new PVC in available zones (requires downtime)
3. Enable regional PD if using GKE: `kubectl patch pv <pv-name> -p '{"spec":{"nodeAffinity":null}}'` (only works for regional persistent disks)

---

### Example 6: Resource Requests Exceed Node Capacity

**Summary: Analytics engine deployment down - 1/1 pods unschedulable**

**Namespace:** analytics
**Status:** Spark driver pod pending for 20+ minutes
**Root cause:** Resource requests exceed node capacity
- Pod requests: 48 CPU cores, 256Gi memory
- Largest node type: n2-standard-32 (32 CPU cores, 128Gi memory)
- No single node can satisfy requirements

**Possible remediations:**
1. Reduce resource requests to fit largest available node type: `kubectl patch deployment spark-driver -n analytics --type='json' -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "30"}, {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "120Gi"}]'`
2. Provision larger nodes: add new node pool with bigger machine type
   - For GKE: Use n2-highmem-64 or custom machine types
   - For EKS: Consider x2iezn.metal or similar high-memory instances
   - For AKS: Use Standard_M128s or memory-optimized series
3. Refactor application to use distributed processing (multiple smaller pods) instead of one large pod
