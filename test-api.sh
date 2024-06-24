curl -XPOST 127.0.0.1:8000/api/investigate -H "Content-Type: application/json" --data "{
  \"source\": \"prometheus\",
  \"source_instance_id\": \"some-instance\",
  \"title\": \"Pod is crash looping.\",
  \"description\": \"Pod default/oomkill-deployment-696dbdbf67-d47z6 (main2) is in waiting state (reason: \\\"CrashLoopBackOff\\\").\",
  \"subject\": {
    \"name\": \"oomkill-deployment-696dbdbf67-d47z6\",
    \"subject_type\": \"deployment\",
    \"namespace\": \"default\",
    \"node\": \"some-node\",
    \"container\": \"main2\",
    \"labels\": {
      \"x\": \"y\",
      \"p\": \"q\"
    },
    \"annotations\": {}
  },
  \"context\":
    {
      \"robusta_issue_id\": \"5b3e2fb1-cb83-45ea-82ec-318c94718e44\"
    },
  \"include_tool_calls\": true,
  \"include_tool_call_results\": true
}"
