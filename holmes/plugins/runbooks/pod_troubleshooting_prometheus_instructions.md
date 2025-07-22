# Pod Scheduling Issues – Troubleshooting Runbook (Kubernetes)

## Goal

Diagnose and remediate pod scheduling issues in Kubernetes clusters. These issues typically manifest as pods stuck in `Pending`, or failing with `CrashLoopBackOff`, `ImagePullBackOff`, or `CreateContainerConfigError`. These are often silent until escalated by users or backlog pressure in deployments.

---

## Workflow

- Scope the pod issues: Leverage kubectl to get context on cluster state and scope accordingly to determine the affected pods and reduce noise.
- Track the current state:  Inspect resource requests, limits, and real-time usage, check for recent changes in replica counts, node conditions, or allocations, detect any resource bottlenecks or scheduling problems
- Investigate metric patterns: Query Prometheus metrics, scoped to the pod, container, or related context, analyze trends over the last 24 hours, correlate with CPU, memory, disk, or network data, and watch for spikes, increases, or cyclic activity
- Kubernetes events: Check recent events, deployments, restarts, or scaling actions, link event timing to issues, and look for failures or warnings
- Scan logs for issues: Review logs from impacted pods or containers for errors or warnings, check for app-level failures or resource issues, include system logs if relevant, match the context to the associated events and Prometheus metrics
- Review external factors: Check dependent services or databases, verify networking and discovery, inspect ingress and load balancing layers, and analyze service mesh data if in use
- Build the story: Use logs, metrics, and events to form and prioritize likely causes, trace the sequence of events to the pod issue, and separate underlying issues from downstream symptoms
- Gauge the effect: Identify impacted users or services, determine the severity and spread, look for downstream or cascading issues, and assess potential business consequences
- Take action: Recommend fixes to resolve the issue, suggest monitoring steps to confirm recovery, propose preventive changes, and highlight any config or scaling adjustments needed


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
