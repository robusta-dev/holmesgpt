KubeContainerWaiting
 [\#](#kubecontainerwaiting)
=================================================

Meaning
 [\#](#meaning)
-----------------------

Container in pod is in Waiting state for too long.

Impact
 [\#](#impact)
---------------------

Service degradation or unavailability.

Diagnosis
 [\#](#diagnosis)
---------------------------

* Check pod events via `kubectl -n $NAMESPACE describe pod $POD`.
* Check pod logs via `kubectl -n $NAMESPACE logs $POD -c $CONTAINER`
* Check for missing files such as configmaps/secrets/volumes
* Check for pod requests, especially special ones such as GPU.
* Check for node taints and capabilities.

Mitigation
 [\#](#mitigation)
-----------------------------

See [Container waiting](https://kubernetes.io/docs/tasks/debug-application-cluster/debug-application/#my-pod-stays-waiting)
