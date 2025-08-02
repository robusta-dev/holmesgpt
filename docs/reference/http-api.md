# HolmesGPT API Reference

## Overview
The HolmesGPT API provides endpoints for automated investigations, workload health checks, and conversational troubleshooting. This document describes each endpoint, its purpose, request fields, and example usage.

---

## Endpoints

### `/api/chat` (POST)
**Description:** General-purpose chat endpoint for interacting with the AI assistant. Supports open-ended questions and troubleshooting.

#### Request Fields

| Field                   | Required | Default | Type      | Description                                      |
|-------------------------|----------|---------|-----------|--------------------------------------------------|
| ask                     | Yes      |         | string    | User's question                                  |
| conversation_history    | No       |         | list      | Conversation history (first message must be system)|
| model                   | No       |         | string    | Model name to use                                |

**Example**
```bash
curl -X POST http://<HOLMES-URL>/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "ask": "What is the status of my cluster?",
    "conversation_history": [
      {"role": "system", "content": "You are a helpful assistant."}
    ]
  }'
```

**Example Response**
```json
{
  "analysis": "Your cluster is healthy. All nodes are ready and workloads are running as expected.",
  "conversation_history": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the status of my cluster?"},
    {"role": "assistant", "content": "Your cluster is healthy. All nodes are ready and workloads are running as expected."}
  ],
  "tool_calls": [...],
  "follow_up_actions": [...]
}
```

---

### `/api/investigate` (POST)
**Description:** Initiate an automated investigation of an issue or incident.

#### Request Fields

| Field                   | Required | Default                                    | Type      | Description                                      |
|-------------------------|----------|--------------------------------------------|-----------|--------------------------------------------------|
| source                  | Yes      |                                            | string    | Source of the issue (e.g., "prometheus")         |
| title                   | Yes      |                                            | string    | Title of the investigation                       |
| description             | Yes      |                                            | string    | Description of the issue                         |
| subject                 | Yes      |                                            | object    | Subject details (e.g., resource info)            |
| context                 | Yes      |                                            | object    | Additional context                               |
| source_instance_id      | No       | "ApiRequest"                               | string    | Source instance identifier                       |
| include_tool_calls      | No       | false                                      | boolean   | Include tool calls in response                   |
| include_tool_call_results| No      | false                                      | boolean   | Include tool call results in response            |
| prompt_template         | No       | "builtin://generic_investigation.jinja2"   | string    | Prompt template to use                           |
| sections                | No       |                                            | object    | Structured output sections                       |
| model                   | No       |                                            | string    | Model name to use                                |

**Example**
```bash
curl -X POST http://<HOLMES-URL>/api/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "source": "prometheus",
    "title": "Pod CrashLoopBackOff",
    "description": "Pod is crashing repeatedly",
    "subject": {"namespace": "default", "pod": "my-pod"},
    "context": {},
    "include_tool_calls": true,
    "model": "gpt-4o"
  }'
```

**Example** Response
```json
{
  "analysis": "The pod 'my-pod' in namespace 'default' is crashing due to an OOMKilled event. Consider increasing memory limits.",
  "sections": {
    "Alert Explanation": "...",
    "Key Findings": "...",
    "Conclusions and Possible Root Causes": "...",
    "Next Steps": "...",
    "App or Infra?": "...",
    "External links": "..."
  },
  "tool_calls": [
    {
      "tool_call_id": "1",
      "tool_name": "kubectl_logs",
      "description": "Fetch pod logs",
      "result": {"logs": "..."}
    }
  ],
  "instructions": [...]
}
```

---

### `/api/stream/investigate` (POST)
**Description:** Same as `/api/investigate`, but returns results as a stream for real-time updates.

#### Request Fields
Same as [`/api/investigate`](#apiinvestigate-post).

**Example**
```bash
curl -N -X POST http://<HOLMES-URL>/api/stream/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "source": "prometheus",
    "title": "Pod CrashLoopBackOff",
    "description": "Pod is crashing repeatedly",
    "subject": {"namespace": "default", "pod": "my-pod"},
    "context": {},
    "include_tool_calls": true,
    "model": "gpt-4o"
  }'
```

**Example** Response (streamed)
```bash
event: start_tool_calling
data: {"tool_name": "kubectl_describe", "id": "call_0"}

event: start_tool_calling
data: {"tool_name": "kubectl_logs", "id": "call_1"}

event: start_tool_calling
data: {"tool_name": "kubectl_previous_logs", "id": "call_2"}

event: start_tool_calling
data: {"tool_name": "kubectl_memory_requests_namespace", "id": "call_3"}

event: tool_calling_result
data: {"tool_call_id": "call_3", "role": "tool", "description": "kubectl get pods -n default -o ...", "name": "kubectl_memory_requests_namespace", "result": {...}}

event: tool_calling_result
data: {"tool_call_id": "call_0", "role": "tool", "description": "kubectl describe pod my-pod -n default", "name": "kubectl_describe", "result": {...}}

event: tool_calling_result
data: {"tool_call_id": "call_2", "role": "tool", "description": "kubectl logs my-pod -n default --previous", "name": "kubectl_previous_logs", "result": {...}}

event: tool_calling_result
data: {"tool_call_id": "call_1", "role": "tool", "description": "kubectl logs my-pod -n default", "name": "kubectl_logs", "result": {...}}

event: ai_answer_end
data: {"sections": {"Alert Explanation": ...}}
```

---

### `/api/issue_chat` (POST)
**Description:** Conversational interface for discussing a specific issue or incident, with context from a previous investigation.

#### Request Fields

| Field                   | Required | Default | Type      | Description                                      |
|-------------------------|----------|---------|-----------|--------------------------------------------------|
| ask                     | Yes      |         | string    | User's question                                  |
| investigation_result    | Yes      |         | object    | Previous investigation result (see below)        |
| issue_type              | Yes      |         | string    | Type of issue                                    |
| conversation_history    | No       |         | list      | Conversation history (first message must be system)|
| model                   | No       |         | string    | Model name to use                                |

**investigation_result** object:
- `result` (string, optional): Previous analysis
- `tools` (list, optional): Tools used/results

**Example**
```bash
curl -X POST http://<HOLMES-URL>/api/issue_chat \
  -H "Content-Type: application/json" \
  -d '{
    "ask": "How do I fix this issue?",
    "investigation_result": {
      "result": "Pod crashed due to OOM.",
      "tools": []
    },
    "issue_type": "CrashLoopBackOff",
    "conversation_history": [
      {"role": "system", "content": "You are a helpful assistant."}
    ]
  }'
```

**Example** Response
```json
{
  "analysis": "To fix the CrashLoopBackOff, increase the memory limit for the pod and check for memory leaks in the application.",
  "conversation_history": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "How do I fix this issue?"},
    {"role": "assistant", "content": "To fix the CrashLoopBackOff, increase the memory limit for the pod and check for memory leaks in the application."}
  ],
  "tool_calls": [...],
  "follow_up_actions": [...]
}
```

---

### `/api/workload_health_check` (POST)
**Description:** Performs a health check on a specified workload (e.g., a Kubernetes deployment).

#### Request Fields

| Field                   | Required | Default                                    | Type      | Description                                      |
|-------------------------|----------|--------------------------------------------|-----------|--------------------------------------------------|
| ask                     | Yes      |                                            | string    | User's question                                  |
| resource                | Yes      |                                            | object    | Resource details (e.g., name, kind)              |
| alert_history_since_hours| No       | 24                                         | float     | How many hours back to check alerts              |
| alert_history           | No       | true                                       | boolean   | Whether to include alert history                 |
| stored_instructions     | No       | true                                       | boolean   | Use stored instructions                          |
| instructions            | No       | []                                         | list      | Additional instructions                          |
| include_tool_calls      | No       | false                                      | boolean   | Include tool calls in response                   |
| include_tool_call_results| No       | false                                      | boolean   | Include tool call results in response            |
| prompt_template         | No       | "builtin://kubernetes_workload_ask.jinja2" | string    | Prompt template to use                           |
| model                   | No       |                                            | string    | Model name to use                                |

**Example**
```bash
curl -X POST http://<HOLMES-URL>/api/workload_health_check \
  -H "Content-Type: application/json" \
  -d '{
    "ask": "Why is my deployment unhealthy?",
    "resource": {"name": "my-deployment", "kind": "Deployment"},
    "alert_history_since_hours": 12
  }'
```

**Example** Response
```json
{
  "analysis": "Deployment 'my-deployment' is unhealthy due to repeated CrashLoopBackOff events.",
  "sections": null,
  "tool_calls": [
    {
      "tool_call_id": "2",
      "tool_name": "kubectl_get_events",
      "description": "Fetch recent events",
      "result": {"events": "..."}
    }
  ],
  "instructions": [...]
}
```

---

### `/api/workload_health_chat` (POST)
**Description:** Conversational interface for discussing the health of a workload.

#### Request Fields

| Field                   | Required | Default | Type      | Description                                      |
|-------------------------|----------|---------|-----------|--------------------------------------------------|
| ask                     | Yes      |         | string    | User's question                                  |
| workload_health_result  | Yes      |         | object    | Previous health check result (see below)         |
| resource                | Yes      |         | object    | Resource details                                 |
| conversation_history    | No       |         | list      | Conversation history (first message must be system)|
| model                   | No       |         | string    | Model name to use                                |

**workload_health_result** object:
- `analysis` (string, optional): Previous analysis
- `tools` (list, optional): Tools used/results

**Example**
```bash
curl -X POST http://<HOLMES-URL>/api/workload_health_chat \
  -H "Content-Type: application/json" \
  -d '{
    "ask": "Check the workload health.",
    "workload_health_result": {
      "analysis": "Previous health check: all good.",
      "tools": []
    },
    "resource": {"name": "my-deployment", "kind": "Deployment"},
    "conversation_history": [
      {"role": "system", "content": "You are a helpful assistant."}
    ]
  }'
```

**Example** Response
```json
{
  "analysis": "The deployment 'my-deployment' is healthy. No recent issues detected.",
  "conversation_history": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Check the workload health."},
    {"role": "assistant", "content": "The deployment 'my-deployment' is healthy. No recent issues detected."}
  ],
  "tool_calls": [...]
}
```

---

### `/api/model` (GET)
**Description:** Returns a list of available AI models that can be used for investigations and chat.

**Example**
```bash
curl http://<HOLMES-URL>/api/model
```

**Example** Response
```json
{
  "model_name": ["gpt-4o", "azure/gpt-4o", "robusta"]
}
```
