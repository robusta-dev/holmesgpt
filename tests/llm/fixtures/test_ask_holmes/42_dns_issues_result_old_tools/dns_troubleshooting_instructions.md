# DNS Troubleshooting Guidelines (Kubernetes)

## Goal
Your primary goal when using these tools is to diagnose DNS resolution issues within a Kubernetes cluster, focusing on identifying common problems like incorrect CoreDNS/kube-dns setup, network policies, or service discovery failures by strictly following the workflow for DNS diagnosis.

*   Use the tools to gather information about the DNS pods, services, and configuration.
*   Clearly present the key findings from the tool outputs in your analysis.
*   Instead of providing next steps to the user, you need to follow the troubleshooting guide to execute the steps.

## Workflow for DNS Diagnosis

1.  **Check CoreDNS/kube-dns Pods:**
    *   Verify that the DNS pods (e.g., CoreDNS or kube-dns) are running in the `kube-system` namespace. Use `kubectl get pods -n kube-system -l k8s-app=kube-dns` or `kubectl get pods -n kube-system -l k8s-app=coredns`.
    *   Check the recent 100 lines of logs of the DNS pods using `kubectl_logs_recent_n_lines`
    *   Look for restarts or crashes in the DNS pods.

2.  **Examine DNS Service:**
    *   Ensure the DNS service is correctly defined: `kubectl get svc kube-dns -n kube-system` (or the equivalent for your DNS provider).
    *   Verify the ClusterIP of the DNS service and the ports (usually 53/UDP and 53/TCP).

3.  **Test DNS Resolution from a Pod:**
    *   Launch a debugging pod (e.g., using `busybox` or `nslookup` tools).
    *   **Inside the debug pod:**
        *   Check `/etc/resolv.conf`:
            *   The `nameserver` should point to the DNS service's ClusterIP.
            *   The `search` path should be appropriate for your namespaces (e.g., `your-namespace.svc.cluster.local svc.cluster.local cluster.local`).
            *   The `options` (like `ndots:5`) can affect resolution behavior.
        *   Attempt to resolve internal cluster names:
            *   A service in the same namespace (e.g., `myservice`).
            *   A service in a different namespace (e.g., `myservice.othernamespace`).
            *   A fully qualified domain name (FQDN) (e.g., `myservice.othernamespace.svc.cluster.local`).
        *   Attempt to resolve external names (e.g., `www.google.com`).
    *   Use tools like `nslookup <hostname>` or `dig <hostname>` for detailed query information.

4.  **Check NetworkPolicies:**
    *   If NetworkPolicies are in place, ensure they allow DNS traffic (to port 53 UDP/TCP) from your application pods to the DNS pods/service.
    *   List NetworkPolicies: `kubectl get networkpolicies --all-namespaces`.
    *   Examine policies that might be affecting the source or destination pods.

5.  **Review CoreDNS Configuration (if applicable):**
    *   Inspect the CoreDNS ConfigMap: `kubectl get configmap coredns -n kube-system -o yaml`.
    *   Look for errors or misconfigurations in the Corefile (e.g., incorrect upstream resolvers, plugin issues).
    *   Inspect the customized CoreDNS ConfigMap: `kubectl get configmap coredns-custom -n kube-system -o yaml`.
    *   Look for errors or misconfigurations in the customized CoreDNS config (e.g., incorrect upstream resolvers, plugin issues).

6.  **Check the DNS trace**
    *   Use findings from the DNS trace to pinpoint where DNS resolution is failing (e.g., query not reaching DNS server, invalid FQDN, or error response from DNS server).


## Synthesize Findings
Based on the outputs from the above steps, describe the DNS issue clearly. For example:
*   "DNS resolution for internal service 'myservice' is failing from pods in namespace 'app-ns'. The CoreDNS pods in `kube-system` are running but show 'connection refused' errors in their logs when trying to reach upstream resolvers."
*   "Pods in namespace 'secure-ns' cannot resolve any hostnames. `/etc/resolv.conf` in these pods is missing the correct `nameserver` entry. This is likely due to a misconfiguration in the pod's `dnsPolicy` or the underlying node's DNS setup."
*   "External DNS resolution is failing cluster-wide. The CoreDNS ConfigMap shows that the `forward` plugin is pointing to an incorrect upstream DNS server IP address."
*   "DNS lookups for 'service-a.namespace-b' are timing out. A NetworkPolicy in 'namespace-b' is blocking egress traffic on port 53 to the kube-dns service."

## Recommend Remediation Steps (Based on Docs)
*   **CRITICAL:** ALWAYS refer to the official Kubernetes DNS debugging guide for detailed troubleshooting and solutions:
    *   Main guide: https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/
    *   CoreDNS specific: https://kubernetes.io/docs/tasks/administer-cluster/dns-custom-nameservers/ (for CoreDNS customization which might be relevant)
*   **DO NOT invent recovery procedures.** Your role is to diagnose and *point* to the correct documentation or standard procedures.
*   Based on the findings, suggest which sections of the documentation are most relevant.
    *   If DNS pods are not running, guide towards checking pod deployment and node health.
    *   If `/etc/resolv.conf` is incorrect, point to sections on Pod `dnsPolicy` and `dnsConfig`.
    *   If NetworkPolicies are suspected, suggest reviewing policy definitions to allow DNS.
    *   If CoreDNS configuration seems problematic, refer to CoreDNS documentation and the Kubernetes guide on customizing it.
    *   If upstream DNS resolution is failing, suggest checking the upstream DNS servers and CoreDNS forward configuration.
