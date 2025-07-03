# HolmesGPT API Reference

## Overview
The HolmesGPT API provides endpoints for automated investigations, workload health checks, and conversational troubleshooting. This document describes each endpoint, its purpose, request fields, and example usage.

---

## Endpoints

### 1. `/api/investigate` (POST)
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

#### Example
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

---

### 2. `/api/stream/investigate` (POST)
**Description:** Same as `/api/investigate`, but returns results as a stream for real-time updates.

#### Request Fields
Same as `/api/investigate`.

#### Example
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

---

### 3. `/api/workload_health_check` (POST)
**Description:** Performs a health check on a specified workload (e.g., a Kubernetes deployment).

#### Request Fields
| Field                   | Required | Default                                    | Type      | Description                                      |
|-------------------------|----------|--------------------------------------------|-----------|--------------------------------------------------|
| ask                     | Yes      |                                            | string    | User's question                                  |
| resource                | Yes      |                                            | object    | Resource details (e.g., name, kind)              |
| alert_history_since_hours| No      | 24                                         | float     | How many hours back to check alerts              |
| alert_history           | No       | true                                       | boolean   | Whether to include alert history                 |
| stored_instrucitons     | No       | true                                       | boolean   | Use stored instructions                          |
| instructions            | No       | []                                         | list      | Additional instructions                          |
| include_tool_calls      | No       | false                                      | boolean   | Include tool calls in response                   |
| include_tool_call_results| No      | false                                      | boolean   | Include tool call results in response            |
| prompt_template         | No       | "builtin://kubernetes_workload_ask.jinja2" | string    | Prompt template to use                           |
| model                   | No       |                                            | string    | Model name to use                                |

#### Example
```bash
curl -X POST http://<HOLMES-URL>/api/workload_health_check \
  -H "Content-Type: application/json" \
  -d '{
    "ask": "Why is my deployment unhealthy?",
    "resource": {"name": "my-deployment", "kind": "Deployment"},
    "alert_history_since_hours": 12
  }'
```

---

### 4. `/api/workload_health_chat` (POST)
**Description:** Conversational interface for discussing the health of a workload. Maintains context across messages.

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

#### Example
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

---

### 5. `/api/issue_chat` (POST)
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

#### Example
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

---

### 6. `/api/chat` (POST)
**Description:** General-purpose chat endpoint for interacting with the AI assistant. Supports open-ended questions and troubleshooting.

#### Request Fields
| Field                   | Required | Default | Type      | Description                                      |
|-------------------------|----------|---------|-----------|--------------------------------------------------|
| ask                     | Yes      |         | string    | User's question                                  |
| conversation_history    | No       |         | list      | Conversation history (first message must be system)|
| model                   | No       |         | string    | Model name to use                                |

#### Example
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

---

### 7. `/api/model` (GET)
**Description:** Returns a list of available AI models that can be used for investigations and chat.

#### Example
```bash
curl http://<HOLMES-URL>/api/model
```

---

