# Node Not Ready – Troubleshooting Runbook (Kubernetes)

## Goal

Diagnose and remediate scenarios where one or more Kubernetes nodes report as `NotReady` or `Unknown`, resulting in pod scheduling failures and application downtime.

---

## Workflow

### 1. **Detect Node Failures**

* Use Prometheus metrics and alerts from the AzureMonitorMetrics toolset.
* Typical symptoms include:
  * Node in `NotReady` or `Unknown` status
  * Unschedulable pods
  * Firing alerts such as `KubeNodeUnreachable`

**Core signals**

| **Metric**                                              | **Use**                 | **Extra Labels**                 |
|---------------------------------------------------------|-------------------------|----------------------------------|
| **kube_node_status_condition**                          | Detect NotReady status  | `node`, `condition`, `status`    |
| **kube_node_status_condition**                          | Detect Unknown status   | `node`, `condition`, `status`    |
| **container_memory_working_set_bytes**                  | Spot OOM conditions     | `container`, `pod`, `namespace`  |
| **node_filesystem_usage / node_filesystem_free_bytes**  | Detect disk pressure    | `device`, `mountpoint`, `fstype` |
| **node_disk_inode_utilization**                         | Detect inode pressure   | `device`, `instance`, `job`      |
| **container_cpu_usage_seconds_total**                   | Diagnose CPU starvation | `container`, `pod`, `namespace`  |


---

### 2. **Contextual Signals and Metadata**

Use metadata from kube-state-metrics and node-exporter to understand node specs and conditions.

**Kube-State Metrics**

| **Metric name**                | **Description**            | **Extra Labels**                         |
|--------------------------------|----------------------------|------------------------------------------|
| **kube_node_status_capacity**  | Node resource capacity     | `node`, `resource`, `unit`               |
| **kube_node_status_condition** | Node status conditions     | `node`, `condition`, `status`            |
| **kube_node_status_allocatable** | Allocatable node resources | `node`, `resource`, `unit`             |
| **kube_node_info**             | Node OS/kernel/arch info   | `node`, `architecture`, `kernel_version` |
| **kube_node_spec_taint**       | Node taints                | `node`, `key`, `effect`                  |


**Node Exporter Metrics**

| **Metric name**                        | **Description**                    | **Extra Labels**                     |
|---------------------------------------|------------------------------------|--------------------------------------|
| **node_cpu_seconds_total**            | CPU usage by mode and core         | `cpu`, `mode`, `instance`, `job`     |
| **node_memory_MemAvailable_bytes**    | Available system memory            | `instance`, `job`                    |
| **node_memory_Cached_bytes**          | Cached memory                      | `instance`, `job`                    |
| **node_memory_MemFree_bytes**         | Free memory                        | `instance`, `job`                    |
| **node_memory_Slab_bytes**            | Slab allocator usage               | `instance`, `job`                    |
| **node_memory_MemTotal_bytes**        | Total system memory                | `instance`, `job`                    |
| **node_netstat_Tcp_RetransSegs**      | TCP retransmissions                | `instance`, `job`                    |
| **node_load1 / load5 / load15**       | System load averages               | `instance`, `job`                    |
| **node_disk_read_bytes_total**        | Disk read throughput               | `device`, `instance`, `job`          |
| **node_disk_written_bytes_total**     | Disk write throughput              | `device`, `instance`, `job`          |
| **node_disk_io_time_seconds_total**   | Disk I/O wait time                 | `device`, `instance`, `job`          |
| **node_filesystem_size_bytes**        | Total filesystem capacity          | `device`, `mountpoint`, `fstype`     |
| **node_filesystem_avail_bytes**       | Available filesystem capacity      | `device`, `mountpoint`, `fstype`     |
| **node_filesystem_readonly**          | Read-only filesystem flags         | `device`, `mountpoint`, `fstype`     |
| **node_network_receive_bytes_total**  | Network ingress throughput         | `device`, `instance`, `job`          |
| **node_network_transmit_bytes_total** | Network egress throughput          | `device`, `instance`, `job`          |
| **node_network_receive_drop_total**   | Dropped inbound packets            | `device`, `instance`, `job`          |
| **node_network_transmit_drop_total**  | Dropped outbound packets           | `device`, `instance`, `job`          |
| **node_vmstat_pgmajfault**            | Major page faults                  | `instance`, `job`                    |
| **node_exporter_build_info**          | Exporter build/version metadata    | `version`, `instance`, `job`         |
| **node_time_seconds**                 | System time                        | `instance`, `job`                    |
| **node_uname_info**                   | Host system name and version info  | `nodename`, `machine`, `release`     |

---

## Synthesize Findings

> **"Node `aks-nodepool1-xyz` is reporting `NotReady` due to memory pressure."**

> **"Multiple nodes exhibit inode saturation, impacting pod scheduling."**

> **"CNI and containerd processes are consuming high CPU; node capacity is insufficient for current workload."**

---

## Remediation Actions

### Immediate Fixes

| Symptom                        | Remediation                                                                              |
| ------------------------------ | ---------------------------------------------------------------------------------------- |
| Disk pressure on `/` or `/var` | SSH/DaemonSet cleanup, check for noisy logging pods, resize disks or enable log rotation |
| Memory pressure / kubelet OOM  | Reduce pod memory requests, taint & evict, restart kubelet or reimage VMSS instance      |
| High CPU usage                 | Identify and tune sidecars/CNIs, upgrade VM size, enable autoscaling                     |
| Network unreachable            | Validate NSG/UdR, verify MTU/routing for CNI, reimage or force update via VMSS           |

---

## Prevention and Best Practices

| Domain                    | Strategy                                                          |
| ------------------------- | ----------------------------------------------------------------- |
| **Capacity Mgmt**         | Use VPA or autoscaler, align node sizes to workload profiles      |
| **Alerting**              | Alerts on node NotReady, disk pressure, memory usage thresholds   |
| **Logging Hygiene**       | Prevent excessive logs from apps; enforce log rotation policies   |
| **Deployment Guardrails** | Use policies to prevent pod overcommit and noisy containers       |
| **Node Upkeep**           | Periodically rotate nodes via rolling upgrade or nodepool reimage |
