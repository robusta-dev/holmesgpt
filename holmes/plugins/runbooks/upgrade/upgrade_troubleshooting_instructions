# AKS Upgrade Troubleshooting Guidelines

## Goal
Your primary goal when using these tools is to diagnose cluster and nodepool upgrade failures within an AKS cluster by strictly following the workflow for AKS upgrade diagnosis.

*   Use the tools to gather information about the cluster configuration and upgrade failure reason.
*   Clearly present the key findings from the tool outputs in your analysis.
*   Instead of providing next steps to the user, you need to follow the troubleshoot guide to execute the steps.

## Workflow for AKS Upgrade Diagnosis

1.  **Check Cluster and Nodepool Status:**
    *   Get the current cluster context - cluster name, resource group, and subscription ID. Get the configuration details for this current cluster only. If there is no cluster context set up, ask the user to set the right AKS cluster context using Azure CLI.
    *   Check the provisioning status of your AKS cluster to see if it's in a Failed state. If the cluster is in a Succeeded or Upgrading state, this means that no recent or ongoing upgrades have failed.
    *   Check the provisioning status of your AKS nodepools. If any nodepools have a Failed status, that means that a recent nodepool upgrade has failed.
    *   If the cluster or nodepool is in a Failed state, check the error message and read any documentation links that may be included in the error message details (starting with aka.ms).

If the cluster is in a Succeeded state, follow the steps below to identify if there are any potential issues which could results in a failed cluster - for example, check for any restrictive PDBs or that outbound connectivity endpoints are blocked. If the cluster is in Failed state, check the error message and follow the steps below for that specific error code.

2. **Error code: 'VMExtensionError_OutBoundConnFail'**
    *   If the upgrade failure error message contains 'VMExtensionError_OutBoundConnFail', this means that the cluster upgrade failed due to one or more essential outbound connectivity endpoints being blocked. Most commonly, this is due to a misconfiguration in a network policy, NSG, or Azure firewall which is denying traffic to the endpoint. Check if any of the required rules/endpoints in https://learn.microsoft.com/en-us/azure/aks/outbound-rules-control-egress#azure-global-required-network-rules are blocked due to a network policy, NSG, or Azure firewall and identify the problematic rule.
    *   Check if the outbound connectivity issue is due to an NSG rule by first getting all of the NSGs in the current subscription. Find the NSGs which have a ResourceGroup which contains both the current resource group and cluster name. For each NSG, list all of the rules and determine if any rule is blocking an essential endpoint in the doc linked above. Do this analysis on behalf of the user and only return the problematic NSG rules.

3. **PDB blocking upgrade: Error code "UnsatisfiablePDB"**
    *   If the upgrade fails due to one or more restrictive PDB, this means that one or more PDBs were set in the cluster which do not allow for any pod disruptions. Get all the PDBs configured on the cluster by running 'kubectl get pdb' and identify all PDBs where MaxUnavailable is set to 0 - if any are found, call them out specifically and ask the customer to follow the guidance in this troubleshooting guide for restrictive PDBs: https://learn.microsoft.com/en-us/troubleshoot/azure/azure-kubernetes/error-codes/unsatisfiablepdb-error.

4. **Quota exhaustion issues: Error code "QuotaExceeded"**
    *   If the upgrade fails due to insufficient quota with error code "QuotaExceeded", this means that your subscription doesn't have available resources that are required for upgrading your cluster. You will need to raise the limit or quota for your subscription by filing a "Service and subscription limits (quotas)" support ticket to increase the quota for compute cores. Provide detailed instructions in the response on how to open a specific "Service and subscription limits" support ticket through the Azure Portal for an AKS cluster.


## Synthesize Findings
Based on the outputs from the above steps, describe the upgrade issue clearly and recommend specific and actionable remediation steps. For example:
*   "Upgrade is failing due to outbound connectivity to x endpoint is being blocked by your NSG rules. Please remove the blocking NSG rule x and retry upgrade."
*   If upgrade is failing due to a restrictive PDB, check how many pods for that deployment are currently deployed. If there is only 1 pod, advise the customer to scale up their replicas to allow for upgrades while maintaining availability. "Upgrade is failing due to a restrictive PDB on your x pods which does not tolerate any disruptions. Please set the minAvailable to allow for 1 pod to be disrupted at a time to allow upgrades while maintaining availability."

## Recommend Remediation Steps (Based on Docs)
*   **CRITICAL:** ALWAYS refer to the official AKS upgrade troubleshooting guide for detailed troubleshooting and solutions: https://learn.microsoft.com/en-us/troubleshoot/azure/azure-kubernetes/create-upgrade-delete/upgrading-or-scaling-does-not-succeed
*   **DO NOT invent recovery procedures.** Your role is to diagnose and *point* to the correct documentation or standard procedures.
*   Based on the findings, suggest which sections of the documentation are most relevant.
    *   If upgrade is failing due to PDB blocking, provide specific guidance from the documentation towards adjusting PDB settings.
    *   If upgrade is failing due to quota exhaustion, provide specific guidance from the documentation towards reviewing resource quotas.
    *   If upgrade is failing due to node issues, provide specific guidance from the documentation towards reviewing node status and health.
    *   If upgrade is failing due to network issues, provide specific guidance from the documentation towards reviewing network configuration.
    *   If upgrade is failing due to other issues, provide specific guidance from the documentation towards reviewing the upgrade logs and configuration.
