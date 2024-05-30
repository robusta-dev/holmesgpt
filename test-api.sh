curl -XPOST 127.0.0.1:8000/api/investigate -H "Content-Type: application/json" --data "{
  \"source\": \"prometheus\",
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
  \"context\": [
    {
      \"type\": \"robusta_issue_id\",
      \"value\": \"0xdeadbeef\"
    }
  ]
}"
