curl -XPOST 127.0.0.1:8000/api/workload_health_check -H "Content-Type: application/json" --data "{
    \"ask\": \"Help me diagnose an issue with the workload default/Deployment/robusta-holmes running in my Kubernetes cluster. Can you assist with identifying potential issues and pinpoint the root cause.\",
    \"resource\": {
        \"name\": \"robusta-holmes\",
        \"namespace\": \"default\",
        \"kind\": \"Deployment\",
        \"node\": null,
        \"container\": null,
        \"cluster\": \"local-kind-cluster\"
    },
    \"alert_history_since_hours\": 1.0,
    \"alert_history\": false,
    \"stored_instrucitons\": true,
    \"instructions\":[],
    \"include_tool_calls\": true,
    \"include_tool_call_results\": true,
    \"prompt_template\": \"builtin://kubernetes_workload_ask.jinja2\"
}"
