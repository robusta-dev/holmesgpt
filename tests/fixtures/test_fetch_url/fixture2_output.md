KubePodCrashLooping
 [\#](#kubepodcrashlooping)
===============================================

Meaning
 [\#](#meaning)
-----------------------

Pod is in CrashLoop which means the app dies or is unresponsive and
kubernetes tries to restart it automatically.

Impact
 [\#](#impact)
---------------------

Service degradation or unavailability.
Inability to do rolling upgrades.
Certain apps will not perform required tasks such as data migrations.

Diagnosis
 [\#](#diagnosis)
---------------------------

* Check template via `kubectl -n $NAMESPACE get pod $POD`.
* Check pod events via `kubectl -n $NAMESPACE describe pod $POD`.
* Check pod logs via `kubectl -n $NAMESPACE logs $POD -c $CONTAINER`
* Check pod template parameters such as:
	+ pod priority
	+ resources \- maybe it tries to use unavailable resource, such as GPU but
	there is limited number of nodes with GPU
	+ readiness and liveness probes may be incorrect \- wrong port or command,
	check is failing too fast due to short timeout for response

Other things to check:

* app responding extremely slow due to resource constraints such as memory too
low, not enough CPU which is required on start
* app waits for other services to start, such as database
* misconfiguration causing app crash on start
* missing files such as configmaps/secrets/volumes
* read only filesystem
* wrong user permissions in container
* lack of special container capabilities (securityContext)
* app is executed in different directory than expected
(for example WORKDIR from Docerkfile is not used in OpenShift)

Mitigation
 [\#](#mitigation)
-----------------------------

Talk with developers or read documentation about the app, ensure to define
sane default values to start the app.

See [Debugging Pods](https://kubernetes.io/docs/tasks/debug-application-cluster/debug-application/#debugging-pods)
