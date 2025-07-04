```bash
kubectl create secret generic fleet-credentials \
  --from-literal=FLEET_URL='https://3461eecc16cc45f5b387e686f8e796c5.apm.us-central1.gcp.cloud.es.io' \
  --from-literal=ENROLLMENT_TOKEN='essu_ZWtremFYbzFZMEpqYkZWdllUUTBjek5EVjFjNlRGQmljalEwZGxwUmMyRlpRbkJJTFV0V2RuQnhRUT09AAAAAPG3k+M=' \
  -n kube-system
```


kubectl create secret generic elastic-apm-credentials \
  --from-literal=APM_SERVER_URL='[<YOUR_APM_SERVER_URL>](https://3461eecc16cc45f5b387e686f8e796c5.apm.us-central1.gcp.cloud.es.io)' \
  --from-literal=SECRET_TOKEN='essu_ZWtremFYbzFZMEpqYkZWdllUUTBjek5EVjFjNlRGQmljalEwZGxwUmMyRlpRbkJJTFV0V2RuQnhRUT09AAAAAPG3k+M='
