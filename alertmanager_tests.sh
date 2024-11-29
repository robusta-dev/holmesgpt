python ./holmes.py investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-label=alertname=TargetDown --alertmanager-label=job=coredns

python ./holmes.py investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-label=alertname=KubeDeploymentReplicasMismatch  --alertmanager-label=deployment=payment-processing-worker

python ./holmes.py investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-label=alertname=KubePodCrashLooping             --alertmanager-label=pod=~payment-processing-worker-.*

python ./holmes.py investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-label=alertname=KubePodNotReady                 --alertmanager-label=pod=user-profile-import

python ./holmes.py investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-label=alertname=KubePodNotReady                 --alertmanager-label="pod=~user-profile-resources-.*" \
--alertmanager-label=alertname=KubeDeploymentReplicasMismatch  --alertmanager-label=deployment=user-profile-resources \
--alertmanager-label=alertname=KubeDeploymentRolloutStuck  --alertmanager-label=deployment=user-profile-resources

python ./holmes.py investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-label=alertname=KubeControllerManagerDown

python ./holmes.py investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-label=alertname=KubeSchedulerDown

python ./holmes.py investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-label=alertname=Watchdog
