# DNS Resolution Failures – Troubleshooting Runbook (Kubernetes)

## Goal

Diagnose and remediate DNS resolution failures within a Kubernetes cluster. Focus on identifying misconfigurations, upstream resolver issues, or blocked traffic leading to DNS errors (e.g., `SERVFAIL`, `NXDOMAIN`, `REFUSED`, `NotImplemented`, `DNSSEC/EDNS` errors).

## Workflow

### 1. **Detect and Quantify DNS Failures**

* Use Prometheus metrics from the AzureMonitorMetrics toolset.

**PromQL Queries**

Node level metrics

| Metric name                    | Description                  | Extra labels           |
|--------------------------------|------------------------------|------------------------|
| **cilium_forward_count_total** | Total forwarded packet count | `direction`            |
| **cilium_forward_bytes_total** | Total forwarded byte count   | `direction`            |
| **cilium_drop_count_total**    | Total dropped packet count   | `direction`, `reason`  |
| **cilium_drop_bytes_total**    | Total dropped byte count     | `direction`, `reason`  |

Pod level metrics

| Metric name                      | Description                                 | Extra Labels                                                                 |
|----------------------------------|---------------------------------------------|------------------------------------------------------------------------------|
| **hubble_dns_queries_total**     | Total DNS requests by query                 | `source` or `destination`, `query`, `qtypes` (query type)                   |
| **hubble_dns_responses_total**   | Total DNS responses by query/response       | `source` or `destination`, `query`, `qtypes` (query type), `rcode`, `ips_returned` |
| **hubble_drop_total**            | Total dropped packet count                  | `source` or `destination`, `protocol`, `reason`                             |
| **hubble_tcp_flags_total**       | Total TCP packets count by flag             | `source` or `destination`, `flag`                                           |
| **hubble_flows_processed_total** | Total network flows processed (L4/L7 traffic) | `source` or `destination`, `protocol`, `verdict`, `type`, `subtype`        |


Query the metrics to determine if there are spikes in errors and where the errors are associated based on node or pod.

---


## Synthesize Findings

Use the combination of metrics and logs to clearly state:

> **"Pods in `X` namespace are experiencing NXDOMAIN errors due to misconfigured `nameserver` entries in `/etc/resolv.conf`."**

> **"CoreDNS is returning `SERVFAIL` for upstream lookups—logs show timeout errors; likely due to unreachable Azure DNS servers."**

> **"High latency and spike in `REFUSED` errors from debug pods in `team-a-ns`, combined with recent NetworkPolicy changes."**

---

## Remediation Actions

### Immediate Fixes

| Symptom                  | Action                                                                 |
| ------------------------ | ---------------------------------------------------------------------- |
| CoreDNS plugin/misconfig | Revert ConfigMap: `kubectl rollout undo deploy coredns -n kube-system` |
| CoreDNS crashloop        | Check logs → Restart pod → Scale replicas                              |
| NetworkPolicy blocks     | Inspect and patch rules allowing DNS (port 53 UDP/TCP)                 |
| Upstream DNS unreachable | Update `forward` plugin in CoreDNS to fallback DNS (e.g., 8.8.8.8)     |
| DNS saturation           | Scale CoreDNS, reduce noisy traffic                                    |
| NXDOMAIN/typos           | Check domain spelling, app DNS caching behavior                        |

---

### Mid-Range Mitigation

| Risk Area            | Recommended Action                                     |
| -------------------- | ------------------------------------------------------ |
| CoreDNS config drift | Use GitOps, `kubectl diff`, or webhook validation      |
| Low observability    | Enable alerts on error spikes (rcode ≠ 0)              |
| Noisy apps           | Rate-limit retries in app logic                        |
| No ownership         | Tag CoreDNS with owner, set alerts for team escalation |

---

## Prevention and Best Practices

| Domain               | Strategy                                                           |
| -------------------- | ------------------------------------------------------------------ |
| **Testing**          | Add DNS checks in CI smoke tests                                   |
| **Alerting**         | Alerts on high `rcode≠0` error rate, p95 latency                   |
| **Runbooks**         | Document common failures and resolution queries                    |
| **Automation**       | Auto-notify teams on risky changes via Logic Apps/MCP              |
| **Infra Resilience** | Deploy multiple DNS replicas, validate cross-zone DNS reachability |
