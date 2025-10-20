{{- define "holmes.awsMcp.fullname" -}}
{{- printf "%s-aws-mcp-server" .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "holmes.awsMcp.labels" -}}
app: {{ include "holmes.awsMcp.fullname" . }}
app.kubernetes.io/name: aws-mcp-server
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: mcp-server
app.kubernetes.io/part-of: holmes
{{- end -}}

{{- define "holmes.awsMcp.selectorLabels" -}}
app: {{ include "holmes.awsMcp.fullname" . }}
app.kubernetes.io/name: aws-mcp-server
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "holmes.awsMcp.serviceUrl" -}}
{{- $namespace := .Values.mcpAddons.aws.config.namespace | default .Release.Namespace -}}
{{- printf "http://%s.%s.svc.cluster.local:8000" (include "holmes.awsMcp.fullname" .) $namespace -}}
{{- end -}}

{{- define "holmes.awsMcp.serviceAccountName" -}}
{{- if .Values.mcpAddons.aws.serviceAccount.create -}}
    {{- default (printf "%s-aws-mcp-sa" .Release.Name) .Values.mcpAddons.aws.serviceAccount.name -}}
{{- else -}}
    {{- default "default" .Values.mcpAddons.aws.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Define the LLM instructions for AWS MCP
*/}}
{{- define "holmes.awsMcp.llmInstructions" -}}
{{- if .Values.mcpAddons.aws.llmInstructions -}}
{{ .Values.mcpAddons.aws.llmInstructions }}
{{- else -}}
IMPORTANT: When investigating issues related to AWS resources or Kubernetes workloads running on AWS, you MUST actively use this MCP server to gather data rather than providing manual instructions to the user.

## Investigation Principles

**ALWAYS follow this investigation flow:**
1. First, gather current state and configuration using AWS APIs
2. Check CloudTrail for recent changes that might have caused the issue
3. Collect metrics and logs from CloudWatch if available
4. Analyze all gathered data before providing conclusions

**Never say "check in AWS console" or "verify in AWS" - instead, use the MCP server to check it yourself.**

## Core Investigation Patterns

### For ANY connectivity or access issues:
1. ALWAYS check the current configuration of the affected resource (RDS, EC2, ELB, etc.)
2. ALWAYS examine security groups and network ACLs
3. ALWAYS query CloudTrail for recent configuration changes
4. Look for patterns in timing between when issues started and when changes were made

### When investigating database issues (RDS):
- Get RDS instance status and configuration: `aws rds describe-db-instances --db-instance-identifier INSTANCE_ID`
- Check security groups attached to RDS: Extract VpcSecurityGroups from the above
- Examine security group rules: `aws ec2 describe-security-groups --group-ids SG_ID`
- Look for recent RDS events: `aws rds describe-events --source-identifier INSTANCE_ID --source-type db-instance`
- Check CloudTrail for security group modifications: `aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=SG_ID`

### When investigating configuration changes:
- Query CloudTrail for recent API calls: `aws cloudtrail lookup-events --start-time TIME --max-items 50`
- Filter by specific resources: `aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=RESOURCE_ID`
- Look for security-related changes: Search for events like RevokeSecurityGroupIngress, AuthorizeSecurityGroupIngress, ModifyDBInstance, etc.
- Identify who made changes: Check UserName and SourceIPAddress in CloudTrail events

### When investigating pod/container issues on EKS:
- Check EKS cluster status: `aws eks describe-cluster --name CLUSTER_NAME`
- Examine node groups: `aws eks describe-nodegroup --cluster-name CLUSTER_NAME --nodegroup-name NODEGROUP`
- Search CloudWatch Container Insights logs if available
- Check EC2 instances hosting the nodes: `aws ec2 describe-instances --instance-ids INSTANCE_ID`

### For networking issues:
- Describe VPC configuration: `aws ec2 describe-vpcs --vpc-ids VPC_ID`
- Check route tables: `aws ec2 describe-route-tables --filters "Name=vpc-id,Values=VPC_ID"`
- Examine network ACLs: `aws ec2 describe-network-acls --filters "Name=vpc-id,Values=VPC_ID"`
- Review security group rules: `aws ec2 describe-security-groups --group-ids SG_ID`

### For load balancer issues:
- Get load balancer status: `aws elbv2 describe-load-balancers --names LB_NAME`
- Check target health: `aws elbv2 describe-target-health --target-group-arn TG_ARN`
- Review listener rules: `aws elbv2 describe-listeners --load-balancer-arn LB_ARN`

## Key Commands for Root Cause Analysis

### CloudTrail Investigation (ALWAYS use when troubleshooting):
Find all recent changes in the last hour:
```
aws cloudtrail lookup-events --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) --max-items 50
```

Find changes to a specific security group:
```
aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=SECURITY_GROUP_ID --max-items 20
```

Find who made changes:
```
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=RevokeSecurityGroupIngress --max-items 10
```

### Resource State Verification:
- Always get the current state before checking what changed
- Compare timestamps of issues with timestamps of changes in CloudTrail
- Look for correlation between configuration changes and issue manifestation

## Important Guidelines:
- If you encounter any AWS resource in the investigation, immediately fetch its details using AWS commands
- Don't assume or guess configurations - retrieve actual data
- When you see connection timeouts or access denied errors, immediately check security groups and CloudTrail
- Always include relevant timestamps when querying for historical data
- If Container Insights is mentioned or available, use it for pod-level investigations

Remember: Your goal is to gather evidence from AWS, not to instruct the user to gather it. Use the MCP server proactively to build a complete picture of what happened.

Some of the available operations include: (there are many other operations, everything included in the aws cli)
- CloudWatch: Query logs, metrics, alarms, and insights
- EC2: Describe instances, security groups, VPCs, networking
- IAM: Check roles, policies, permissions
- RDS: Database metrics, performance insights, configurations
- ECS/EKS: Container and Kubernetes cluster management
- S3: Bucket operations and object management
- Lambda: Function invocations and logs
- Organizations: Billing and cost analysis

Example commands:
- aws logs describe-log-groups
- aws logs filter-log-events --log-group-name <group> --filter-pattern "ERROR"
- aws ec2 describe-instances --instance-ids <id>
- aws iam simulate-principal-policy --policy-source-arn <arn>
- aws rds describe-db-instances
- aws cloudwatch get-metric-statistics
- aws ce get-cost-and-usage
{{- end -}}
{{- end -}}
