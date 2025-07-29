# Kubernetes DNS Troubleshooting Guide

## Step 1: Check CoreDNS Status
Run `kubectl get pods -n kube-system -l k8s-app=kube-dns` to verify CoreDNS pods are running.

## Step 2: Test DNS Resolution
Use a test pod to verify DNS resolution:
```bash
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default
```

## Step 3: Check CoreDNS Logs
Review CoreDNS logs for errors:
```bash
kubectl logs -n kube-system -l k8s-app=kube-dns
```

## Step 4: Verify DNS ConfigMap
Check the CoreDNS configuration:
```bash
kubectl get configmap coredns -n kube-system -o yaml
```
