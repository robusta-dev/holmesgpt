#!/usr/bin/env python3
"""
Holmes Operator for Kubernetes

This operator manages HealthCheck and ScheduledHealthCheck CRDs.
- HealthCheck: One-time execution checks
- ScheduledHealthCheck: Recurring checks on a cron schedule
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import kopf
import requests  # type: ignore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from kubernetes import client, config as k8s_config

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class HolmesCheckOperator:
    """Main operator class for managing health checks."""

    def __init__(self):
        """Initialize the operator with scheduler and configuration."""
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.holmes_api_url = os.getenv("HOLMES_API_URL", "http://holmes-api:8080")

        # Track active scheduled jobs
        self.active_jobs: Dict[str, str] = {}  # job_id -> check_name

        logger.info(f"Holmes operator initialized with API URL: {self.holmes_api_url}")

    def execute_check(
        self, name: str, namespace: str, spec: Dict[str, Any], is_one_time: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a health check by calling the Holmes API.

        Args:
            name: Name of the HealthCheck resource
            namespace: Namespace of the HealthCheck resource
            spec: Spec of the HealthCheck resource
            is_one_time: Whether this is a one-time check (vs scheduled)

        Returns:
            Dict containing the execution result
        """
        check_identifier = f"{namespace}/{name}"
        logger.info(f"Executing check: {check_identifier}")

        # Prepare the request
        check_request = {
            "query": spec["query"],
            "timeout": spec.get("timeout", 30),
            "mode": spec.get("mode", "monitor"),
            "destinations": spec.get("destinations", []),
        }

        try:
            # Call Holmes API
            response = requests.post(
                f"{self.holmes_api_url}/api/check/execute",
                json=check_request,
                headers={"X-Check-Name": check_identifier},
                timeout=spec.get("timeout", 30) + 10,
            )
            response.raise_for_status()
            result = response.json()

            # Log the result
            logger.info(
                f"Check {check_identifier} completed: {result.get('status', 'unknown')}"
            )

            return result

        except requests.Timeout:
            logger.error(f"Check {check_identifier} timed out")
            return {
                "status": "error",
                "message": "Check execution timed out",
                "error": "TimeoutError",
            }
        except Exception as e:
            logger.error(f"Error executing check {check_identifier}: {e}")
            return {
                "status": "error",
                "message": f"Check execution failed: {str(e)}",
                "error": str(e),
            }

    def update_healthcheck_status(
        self,
        name: str,
        namespace: str,
        phase: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update the HealthCheck CRD status.

        Args:
            name: Name of the HealthCheck resource
            namespace: Namespace of the HealthCheck resource
            phase: Current phase (Pending, Running, Completed)
            result: Execution result from API (optional)
        """
        try:
            # Load k8s config
            try:
                k8s_config.load_incluster_config()
            except Exception:
                k8s_config.load_kube_config()

            api = client.CustomObjectsApi()

            # Prepare status update
            now = datetime.utcnow().isoformat() + "Z"
            status: Dict[str, Any] = {
                "phase": phase,
            }

            if phase == "Running":
                status["startTime"] = now
            elif phase == "Completed" and result:
                status["completionTime"] = now
                status["result"] = result.get("status", "unknown")
                status["message"] = result.get("message", "")
                status["rationale"] = result.get("rationale", "")
                status["duration"] = result.get("duration", 0)

                # Update conditions
                status["conditions"] = [
                    {
                        "type": "Complete",
                        "status": "True",
                        "lastTransitionTime": now,
                        "reason": result.get("status", "unknown").title(),
                        "message": result.get("rationale", result.get("message", "")),
                    }
                ]

            # Update the status
            api.patch_namespaced_custom_object_status(
                group="holmes.robusta.dev",
                version="v1alpha1",
                namespace=namespace,
                plural="healthchecks",
                name=name,
                body={"status": status},
            )

            logger.debug(f"Updated HealthCheck status for {namespace}/{name}: {phase}")

        except Exception as e:
            logger.error(
                f"Failed to update HealthCheck status for {namespace}/{name}: {e}"
            )

    def update_scheduled_status(
        self, name: str, namespace: str, result: Dict[str, Any], check_name: str
    ) -> None:
        """
        Update the ScheduledHealthCheck CRD status with execution results.

        Args:
            name: Name of the ScheduledHealthCheck resource
            namespace: Namespace of the ScheduledHealthCheck resource
            result: Execution result from API
            check_name: Name of the HealthCheck resource that was created
        """
        try:
            # Load k8s config
            try:
                k8s_config.load_incluster_config()
            except Exception:
                k8s_config.load_kube_config()

            api = client.CustomObjectsApi()

            # Get current resource to preserve history
            try:
                current = api.get_namespaced_custom_object(
                    group="holmes.robusta.dev",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="scheduledhealthchecks",
                    name=name,
                )
                current_status = current.get("status", {})
                history = current_status.get("history", [])
            except Exception:
                history = []

            # Add new result to history (keep last 10)
            history.insert(
                0,
                {
                    "executionTime": datetime.utcnow().isoformat() + "Z",
                    "result": result.get("status", "unknown"),
                    "duration": result.get("duration", 0),
                    "checkName": check_name,
                },
            )
            history = history[:10]  # Keep only last 10 executions

            # Prepare status update
            now = datetime.utcnow().isoformat() + "Z"
            status = {
                "lastScheduleTime": now,
                "lastResult": result.get("status", "unknown"),
                "message": result.get("message", ""),
                "history": history,
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True" if result.get("status") == "pass" else "False",
                        "lastTransitionTime": now,
                        "reason": result.get("status", "unknown").title(),
                        "message": result.get("rationale", result.get("message", "")),
                    }
                ],
            }

            # Update successful time if check passed
            if result.get("status") == "pass":
                status["lastSuccessfulTime"] = now
            elif current_status.get("lastSuccessfulTime"):
                status["lastSuccessfulTime"] = current_status["lastSuccessfulTime"]

            # Update the status
            api.patch_namespaced_custom_object_status(
                group="holmes.robusta.dev",
                version="v1alpha1",
                namespace=namespace,
                plural="scheduledhealthchecks",
                name=name,
                body={"status": status},
            )

            logger.debug(f"Updated ScheduledHealthCheck status for {namespace}/{name}")

        except Exception as e:
            logger.error(
                f"Failed to update ScheduledHealthCheck status for {namespace}/{name}: {e}"
            )

    def create_healthcheck_from_scheduled(
        self, scheduled_name: str, namespace: str, check_spec: Dict[str, Any]
    ) -> str:
        """
        Create a HealthCheck resource from a ScheduledHealthCheck.

        Args:
            scheduled_name: Name of the ScheduledHealthCheck
            namespace: Namespace to create the HealthCheck in
            check_spec: The checkSpec from the ScheduledHealthCheck

        Returns:
            Name of the created HealthCheck resource
        """
        try:
            # Load k8s config
            try:
                k8s_config.load_incluster_config()
            except Exception:
                k8s_config.load_kube_config()

            api = client.CustomObjectsApi()

            # Generate unique name for the HealthCheck
            check_name = f"{scheduled_name}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

            # Create HealthCheck resource
            healthcheck: Dict[str, Any] = {
                "apiVersion": "holmes.robusta.dev/v1alpha1",
                "kind": "HealthCheck",
                "metadata": {
                    "name": check_name,
                    "namespace": namespace,
                    "labels": {
                        "holmes.robusta.dev/scheduled-by": scheduled_name,
                    },
                    "ownerReferences": [
                        {
                            "apiVersion": "holmes.robusta.dev/v1alpha1",
                            "kind": "ScheduledHealthCheck",
                            "name": scheduled_name,
                            "uid": "",  # Will be filled by k8s
                            "controller": True,
                            "blockOwnerDeletion": True,
                        }
                    ],
                },
                "spec": check_spec,
            }

            # Get the ScheduledHealthCheck UID for owner reference
            try:
                scheduled = api.get_namespaced_custom_object(
                    group="holmes.robusta.dev",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="scheduledhealthchecks",
                    name=scheduled_name,
                )
                healthcheck["metadata"]["ownerReferences"][0]["uid"] = scheduled[
                    "metadata"
                ]["uid"]
            except Exception as e:
                logger.warning(f"Could not set owner reference: {e}")
                # Remove owner reference if we can't get the UID
                del healthcheck["metadata"]["ownerReferences"]

            # Create the HealthCheck
            api.create_namespaced_custom_object(
                group="holmes.robusta.dev",
                version="v1alpha1",
                namespace=namespace,
                plural="healthchecks",
                body=healthcheck,
            )

            logger.info(
                f"Created HealthCheck {check_name} from ScheduledHealthCheck {scheduled_name}"
            )
            return check_name

        except Exception as e:
            logger.error(
                f"Failed to create HealthCheck from ScheduledHealthCheck {scheduled_name}: {e}"
            )
            raise

    def execute_scheduled_check(
        self, name: str, namespace: str, spec: Dict[str, Any]
    ) -> None:
        """
        Execute a scheduled check by creating a HealthCheck resource.

        Args:
            name: Name of the ScheduledHealthCheck resource
            namespace: Namespace of the ScheduledHealthCheck resource
            spec: Spec of the ScheduledHealthCheck resource
        """
        try:
            # Create a HealthCheck resource
            check_name = self.create_healthcheck_from_scheduled(
                name, namespace, spec["checkSpec"]
            )

            # The HealthCheck will be handled by its own operator handlers
            # We just need to track that we created it
            logger.info(
                f"Scheduled check {namespace}/{name} created HealthCheck {check_name}"
            )

        except Exception as e:
            logger.error(f"Failed to execute scheduled check {namespace}/{name}: {e}")
            # Update status with error
            self.update_scheduled_status(
                name,
                namespace,
                {
                    "status": "error",
                    "message": f"Failed to create HealthCheck: {str(e)}",
                    "error": str(e),
                },
                "unknown",
            )

    def schedule_check(self, name: str, namespace: str, spec: Dict[str, Any]) -> str:
        """
        Schedule a health check based on its spec.

        Args:
            name: Name of the ScheduledHealthCheck resource
            namespace: Namespace of the ScheduledHealthCheck resource
            spec: Spec of the ScheduledHealthCheck resource

        Returns:
            Job ID for the scheduled check
        """
        # Generate unique job ID based on namespace, name, and spec hash
        spec_hash = hashlib.md5(str(spec).encode()).hexdigest()[:8]
        job_id = f"{namespace}-{name}-{spec_hash}"

        # Remove existing job if it exists
        if job_id in self.active_jobs:
            logger.info(f"Removing existing job: {job_id}")
            self.scheduler.remove_job(job_id)
            del self.active_jobs[job_id]

        # Don't schedule if disabled
        if not spec.get("enabled", True):
            logger.info(
                f"ScheduledHealthCheck {namespace}/{name} is disabled, not scheduling"
            )
            return job_id

        # Get schedule
        schedule = spec.get("schedule")
        if not schedule:
            logger.error(
                f"No schedule provided for ScheduledHealthCheck {namespace}/{name}"
            )
            return job_id

        try:
            # Add the job to scheduler
            self.scheduler.add_job(
                self.execute_scheduled_check,
                CronTrigger.from_crontab(schedule),
                args=[name, namespace, spec],
                id=job_id,
                name=f"ScheduledHealthCheck: {namespace}/{name}",
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
                coalesce=True,  # Coalesce missed jobs
            )

            self.active_jobs[job_id] = f"{namespace}/{name}"
            logger.info(f"Scheduled check {namespace}/{name} with schedule: {schedule}")

        except Exception as e:
            logger.error(f"Failed to schedule check {namespace}/{name}: {e}")

        return job_id

    def unschedule_check(self, name: str, namespace: str) -> None:
        """
        Remove a scheduled health check.

        Args:
            name: Name of the ScheduledHealthCheck resource
            namespace: Namespace of the ScheduledHealthCheck resource
        """
        # Find and remove all jobs for this check
        jobs_to_remove = []
        for job_id, check_name in self.active_jobs.items():
            if check_name == f"{namespace}/{name}":
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            try:
                self.scheduler.remove_job(job_id)
                del self.active_jobs[job_id]
                logger.info(f"Unscheduled check: {namespace}/{name} (job: {job_id})")
            except Exception as e:
                logger.error(f"Failed to unschedule job {job_id}: {e}")

    def cleanup(self):
        """Clean up resources."""
        self.scheduler.shutdown(wait=False)


# Create global operator instance
operator = HolmesCheckOperator()


@kopf.on.startup()
def startup_handler(**kwargs):
    """Initialize operator on startup."""
    logger.info("Holmes operator starting up...")

    # Load k8s config
    try:
        k8s_config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config")
    except Exception:
        k8s_config.load_kube_config()
        logger.info("Loaded local Kubernetes config")


@kopf.on.cleanup()
def cleanup_handler(**kwargs):
    """Clean up on shutdown."""
    logger.info("Holmes operator shutting down...")
    operator.cleanup()


# ============================================================================
# HealthCheck (one-time execution) handlers
# ============================================================================


@kopf.on.create("holmes.robusta.dev", "v1alpha1", "healthchecks")
@kopf.on.resume("holmes.robusta.dev", "v1alpha1", "healthchecks")
def handle_healthcheck_create(spec: Dict, name: str, namespace: str, **kwargs):
    """
    Handle HealthCheck creation - execute immediately.

    HealthChecks are one-time execution checks that run immediately when created.
    """
    logger.info(f"Handling HealthCheck creation: {namespace}/{name}")

    # Update status to Running
    operator.update_healthcheck_status(name, namespace, "Running")

    # Execute the check
    result = operator.execute_check(name, namespace, spec, is_one_time=True)

    # Update status to Completed with results
    operator.update_healthcheck_status(name, namespace, "Completed", result)

    return {"executed": True, "result": result.get("status", "unknown")}


@kopf.on.update(
    "holmes.robusta.dev",
    "v1alpha1",
    "healthchecks",
    annotations={"holmes.robusta.dev/run-now": kopf.PRESENT},
)
def rerun_healthcheck(name: str, namespace: str, spec: Dict, **kwargs):
    """
    Re-run a HealthCheck when the run-now annotation is added.

    This allows re-executing a completed HealthCheck for testing or troubleshooting.
    """
    logger.info(f"Re-running HealthCheck: {namespace}/{name}")

    # Update status to Running
    operator.update_healthcheck_status(name, namespace, "Running")

    # Execute the check
    result = operator.execute_check(name, namespace, spec, is_one_time=True)

    # Update status to Completed with results
    operator.update_healthcheck_status(name, namespace, "Completed", result)

    # Remove the annotation after execution
    api = client.CustomObjectsApi()
    api.patch_namespaced_custom_object(
        group="holmes.robusta.dev",
        version="v1alpha1",
        namespace=namespace,
        plural="healthchecks",
        name=name,
        body={"metadata": {"annotations": {"holmes.robusta.dev/run-now": None}}},
    )


# ============================================================================
# ScheduledHealthCheck (recurring execution) handlers
# ============================================================================


@kopf.on.create("holmes.robusta.dev", "v1alpha1", "scheduledhealthchecks")
@kopf.on.update("holmes.robusta.dev", "v1alpha1", "scheduledhealthchecks")
@kopf.on.resume("holmes.robusta.dev", "v1alpha1", "scheduledhealthchecks")
def handle_scheduled_healthcheck(spec: Dict, name: str, namespace: str, **kwargs):
    """
    Handle ScheduledHealthCheck CRD create/update/resume events.

    This is the main reconciliation loop for ScheduledHealthCheck resources.
    The resume handler ensures existing resources are processed on operator startup.
    """
    logger.info(f"Handling ScheduledHealthCheck: {namespace}/{name}")

    # Schedule or reschedule the check
    job_id = operator.schedule_check(name, namespace, spec)

    # Return the job ID to store in the resource status
    return {"jobId": job_id}


@kopf.on.delete("holmes.robusta.dev", "v1alpha1", "scheduledhealthchecks")
def delete_scheduled_healthcheck(name: str, namespace: str, **kwargs):
    """
    Handle ScheduledHealthCheck deletion.

    Clean up any scheduled jobs for the deleted resource.
    """
    logger.info(f"Deleting ScheduledHealthCheck: {namespace}/{name}")
    operator.unschedule_check(name, namespace)


@kopf.on.field(
    "holmes.robusta.dev", "v1alpha1", "scheduledhealthchecks", field="spec.enabled"
)
def handle_scheduled_enabled_change(
    old, new, name: str, namespace: str, spec: Dict, **kwargs
):
    """
    Handle changes to the enabled field for ScheduledHealthCheck.

    This allows users to enable/disable scheduled checks without deleting them.
    """
    if old is None:
        # Field was just added, use default behavior
        return

    if not new and old:
        # Check was disabled
        logger.info(f"Disabling ScheduledHealthCheck: {namespace}/{name}")
        operator.unschedule_check(name, namespace)
    elif new and not old:
        # Check was enabled
        logger.info(f"Enabling ScheduledHealthCheck: {namespace}/{name}")
        operator.schedule_check(name, namespace, spec)


# For testing purposes, allow running scheduled checks immediately
@kopf.on.update(
    "holmes.robusta.dev",
    "v1alpha1",
    "scheduledhealthchecks",
    annotations={"holmes.robusta.dev/run-now": kopf.PRESENT},
)
def run_scheduled_check_now(name: str, namespace: str, spec: Dict, **kwargs):
    """
    Run a scheduled check immediately when the run-now annotation is added.

    This is useful for testing or forcing an immediate check execution.
    """
    logger.info(f"Running scheduled check immediately: {namespace}/{name}")
    operator.execute_scheduled_check(name, namespace, spec)

    # Remove the annotation after execution
    api = client.CustomObjectsApi()
    api.patch_namespaced_custom_object(
        group="holmes.robusta.dev",
        version="v1alpha1",
        namespace=namespace,
        plural="scheduledhealthchecks",
        name=name,
        body={"metadata": {"annotations": {"holmes.robusta.dev/run-now": None}}},
    )


if __name__ == "__main__":
    # Run the operator
    # In production, this would typically be run with:
    # kopf run -A --standalone operator.py
    import sys

    logger.info("Starting Holmes operator...")
    sys.exit(kopf.cli.main())
