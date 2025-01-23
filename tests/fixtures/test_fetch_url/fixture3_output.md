KubeContainerWaiting
 \#
========================

Meaning
 \#
-----------

Container in pod is in Waiting state for too long.

Impact
 \#
----------

Service degradation or unavailability.

Diagnosis
 \#
-------------

* Check pod events via `kubectl -n $NAMESPACE describe pod $POD`.
* Check pod logs via `kubectl -n $NAMESPACE logs $POD -c $CONTAINER`
* Check for missing files such as configmaps/secrets/volumes
* Check for pod requests, especially special ones such as GPU.
* Check for node taints and capabilities.

Mitigation
 \#
--------------

See Container waiting
