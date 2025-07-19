# Pod Scheduling Issues – Troubleshooting Runbook (Kubernetes)

## Goal

Diagnose and remediate pod scheduling issues in Kubernetes clusters. These issues typically manifest as pods stuck in `Pending`, or failing with `CrashLoopBackOff`, `ImagePullBackOff`, or `CreateContainerConfigError`. These are often silent until escalated by users or backlog pressure in deployments.

---

## Workflow

### 1. **Detect Pod Scheduling Failures**

Use Prometheus metrics and kube-state metrics to detect stalled or failing pods.

#### Pod-level kube-state metrics

| **Metric name**                                            | **Description**                            | **Extra Labels**                          |
| ---------------------------------------------------------- | ------------------------------------------ | ----------------------------------------- |
| **kube_pod_container_status_last_terminated_reason** | Last container termination reason          | `pod`, `container`, `reason`              |
| **kube_pod_container_status_restarts_total**          | Total container restarts                   | `pod`, `container`, `namespace`           |
| **kube_pod_container_resource_requests**               | Requested resources per container          | `pod`, `container`, `resource`            |
| **kube_pod_status_phase**                               | Current pod phase (Pending, Running, etc.) | `pod`, `phase`, `namespace`               |
| **kube_pod_container_resource_limits**                 | Resource limits per container              | `pod`, `container`, `resource`            |
| **kube_pod_info**                                        | Static pod info including node & IP        | `pod`, `node`, `namespace`                |
| **kube_pod_owner**                                       | Pod owner reference                        | `pod`, `owner_kind`, `owner_name`         |
| **kube_pod_labels**                                      | Pod labels                                 | `pod`, `label_*`, `namespace`             |
| **kube_pod_annotations**                                 | Pod annotations                            | `pod`, `annotation_*`, `namespace`        |
| **kube_pod_container_status_waiting_reason**          | Waiting status reasons (e.g. ErrImagePull) | `pod`, `container`, `reason`, `namespace` |
| **kube_pod_container_info**                             | Co**_**                                   |                                           |


#### Container cAdvisor metrics

| **Metric name**                                           | **Description**                             | **Extra Labels**                             |
| --------------------------------------------------------- | ------------------------------------------- | -------------------------------------------- |
| **container_spec_cpu_period**                          | CPU period for CFS scheduler                | `container`, `pod`, `namespace`, `image`     |
| **container_spec_cpu_quota**                           | CPU quota for CFS scheduler                 | `container`, `pod`, `namespace`, `image`     |
| **container_cpu_usage_seconds_total**                 | Total CPU time used by the container        | `container`, `pod`, `namespace`, `mode`      |
| **container_memory_rss**                                | Resident memory used                        | `container`, `pod`, `namespace`              |
| **container_memory_working_set_bytes**                | Working set memory (RSS + cache - inactive) | `container`, `pod`, `namespace`              |
| **container_memory_cache**                              | Page cache memory                           | `container`, `pod`, `namespace`              |
| **container_memory_swap**                               | Swap memory usage                           | `container`, `pod`, `namespace`              |
| **container_memory_usage_bytes**                       | Total memory usage                          | `container`, `pod`, `namespace`              |
| **container_cpu_cfs_throttled_periods_total**        | CPU throttling count                        | `container`, `pod`, `namespace`              |
| **container_cpu_cfs_periods_total**                   | Total CFS scheduling periods                | `container`, `pod`, `namespace`              |
| **container_network_receive_bytes_total**             | Total network bytes received                | `container`, `interface`, `namespace`, `pod` |
| **container_network_transmit_bytes_total**            | Total network bytes sent                    | `container`, `interface`, `namespace`, `pod` |
| **container_network_receive_packets_total**           | Network packets received                    | `container`, `interface`, `namespace`, `pod` |
| **container_network_transmit_packets_total**          | Network packets sent                        | `container`, `interface`, `namespace`, `pod` |
| **container_network_receive_packets_dropped_total**  | Dropped received packets                    | `container`, `interface`, `namespace`, `pod` |
| **container_network_transmit_packets_dropped_total** | Dropped sent packets                        | `container`, `interface`, `namespace`, `pod` |
| **container_fs_reads_total**                           | Filesystem read ops                         | `container`, `device`, `namespace`, `pod`    |
| **container_fs_writes_total**                          | Filesystem write ops                        | `container`, `device`, `namespace`, `pod`    |
| **container_fs_reads_bytes_total**                    | Bytes read from filesystem                  | `container`, `device`, `namespace`, `pod`    |
| **container_fs_writes_bytes_total**                   | Bytes written to filesystem                 | `container`, `device`, `namespace`, `pod`    |

---

## Synthesize Findings

The agent workflow includes:

* Correlating metrics to cluster time range, pod, and node.
* Validating scheduling constraints: `requests`, `limits`, `nodeSelector`, `affinity`, `taints`, `zones`.
* Checking node labels and taints via `kube_node_labels` and `kube_node_taint`.
* Highlighting failed scheduling messages from Kubernetes Events.

### Common Root Cause Patterns

| Symptom                                 | Likely Root Cause                        |
| --------------------------------------- | ---------------------------------------- |
| High retries + "insufficient cpu"       | Resource over-request                    |
| "Taint not tolerated"                   | Missing toleration                       |
| "Didn't match selector" + 0 valid nodes | Node selector or affinity misalignment   |
| Scheduling success + repeated crashes   | Likely application bug or resource issue |

---

## Remediation Actions

### Immediate Fixes

| Scenario            | Action                                                           |
| ------------------- | ---------------------------------------------------------------- |
| Resource too high   | Reduce CPU/memory requests or use larger node pool               |
| Taint mismatch      | Add toleration or remove taint from nodes                        |
| Affinity too strict | Loosen `requiredDuringScheduling` to `preferredDuringScheduling` |
| Zonal pinning issue | Remove zone constraints or redeploy in a healthy zone            |
| Image pull issue    | Fix image reference or credentials; retry                        |

### Mid-Range Strategy

| Fix Type                  | Strategy                                                                |
| ------------------------- | ----------------------------------------------------------------------- |
| Capacity planning         | Prometheus dashboards for scheduler retries, pressure                   |
| Proactive taint mapping   | Define node pool conventions for taint/toleration logic                 |
| Deployment best practices | Enforce CI checks for affinity, selector, and resource config           |
| Priority class usage      | Use `PriorityClass` and preemption for critical workloads               |
| Retina visualizations     | Analyze scheduler latency and constraints with Retina dashboard views   |
| Auto-remediation          | Logic App / Azure Function to auto-tag frequent failures (e.g. Pending) |

---

## Prevention and Best Practices

* Define standard limits/requests across namespaces.
* Periodically validate node inventory against workload requirements.
* Integrate scheduling error detection into GitOps and CI pipelines.
* Alert on prolonged Pending pods or spike in scheduler retry metrics.
* Ensure each node pool has clear workload purpose, label, and taint logic.