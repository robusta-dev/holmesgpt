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
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import kopf
import requests  # type: ignore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from kubernetes import client, config as k8s_config
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable format like 2s, 1.5m, 2h"""
    if seconds < 60:
        return f"{seconds:.1f}s" if seconds % 1 else f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m" if minutes % 1 else f"{int(minutes)}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h" if hours % 1 else f"{int(hours)}h"


# Prometheus metrics
checks_scheduled_total = Counter(
    "holmes_checks_scheduled_total",
    "Total number of scheduled checks",
    ["namespace", "name"],
)
checks_executed_total = Counter(
    "holmes_checks_executed_total",
    "Total number of executed checks",
    ["namespace", "name", "type"],
)
checks_failed_total = Counter(
    "holmes_checks_failed_total",
    "Total number of failed checks",
    ["namespace", "name", "type"],
)
check_duration_seconds = Histogram(
    "holmes_check_duration_seconds",
    "Check execution duration in seconds",
    ["namespace", "name", "type"],
)
scheduled_checks_active = Gauge(
    "holmes_scheduled_checks_active", "Number of active scheduled checks"
)


class HolmesCheckOperator:
    """Main operator class for managing health checks."""

    def __init__(self) -> None:
        """Initialize the operator with scheduler and configuration."""
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.holmes_api_url = os.getenv("HOLMES_API_URL", "http://holmes-api:8080")

        # Track active scheduled jobs
        self.active_jobs: Dict[str, str] = {}  # job_id -> check_name

        # Start Prometheus metrics server
        metrics_port = int(os.getenv("METRICS_PORT", "8080"))
        start_http_server(metrics_port)
        logger.info(f"Started Prometheus metrics server on port {metrics_port}")

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
            "timeout": spec.get("timeout", 300),
            "mode": spec.get("mode", "monitor"),
            "destinations": spec.get("destinations", []),
        }

        # Include model if specified
        if spec.get("model"):
            check_request["model"] = spec["model"]

        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 2  # seconds

        try:
            for attempt in range(max_retries):
                try:
                    # Call Holmes API
                    response = requests.post(
                        f"{self.holmes_api_url}/api/check/execute",
                        json=check_request,
                        headers={"X-Check-Name": check_identifier},
                        timeout=spec.get("timeout", 300) + 10,
                    )
                    response.raise_for_status()
                    result = response.json()
                    break  # Success, exit retry loop
                except (requests.ConnectionError, requests.HTTPError) as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (
                            2**attempt
                        )  # Exponential backoff: 2, 4, 8 seconds
                        logger.warning(
                            f"Check {check_identifier} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {delay} seconds..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        # Final attempt failed
                        raise
            else:
                # This should never happen as we raise on final failure, but makes mypy happy
                raise Exception("All retry attempts failed")

            # Log the result
            logger.info(
                f"Check {check_identifier} completed: {result.get('status', 'unknown')}"
            )

            # Update metrics
            check_type = "scheduled" if not is_one_time else "one_time"
            checks_executed_total.labels(
                namespace=namespace, name=name, type=check_type
            ).inc()
            if result.get("status") == "fail":
                checks_failed_total.labels(
                    namespace=namespace, name=name, type=check_type
                ).inc()
            if result.get("duration"):
                check_duration_seconds.labels(
                    namespace=namespace, name=name, type=check_type
                ).observe(result["duration"])

            return result

        except requests.Timeout:
            logger.error(f"Check {check_identifier} timed out")
            check_type = "scheduled" if not is_one_time else "one_time"
            checks_failed_total.labels(
                namespace=namespace, name=name, type=check_type
            ).inc()
            return {
                "status": "error",
                "message": "Check execution timed out",
                "error": "TimeoutError",
            }
        except Exception as e:
            logger.error(f"Error executing check {check_identifier}: {e}")
            check_type = "scheduled" if not is_one_time else "one_time"
            checks_failed_total.labels(
                namespace=namespace, name=name, type=check_type
            ).inc()
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
        spec: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update the HealthCheck CRD status.

        Args:
            name: Name of the HealthCheck resource
            namespace: Namespace of the HealthCheck resource
            phase: Current phase (Pending, Running, Completed)
            result: Execution result from API (optional)
            spec: Resource spec for extracting query (optional)
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

            # Add shortQuery for display if we have the spec
            if spec:
                query = spec.get("query", "")
                if len(query) > 30:
                    status["shortQuery"] = query[:27] + "..."
                else:
                    status["shortQuery"] = query

            if phase == "Running":
                status["startTime"] = now
            elif phase in ["Passed", "Failed", "Error"] and result:
                status["completionTime"] = now
                status["message"] = result.get("message", "")
                status["rationale"] = result.get("rationale", "")
                # Format duration as human-readable string (2s, 1.5m, etc)
                duration = result.get("duration", 0)
                status["duration"] = format_duration(duration) if duration else "0s"

                # Store the actual model used
                if result.get("model_used"):
                    status["modelUsed"] = result.get("model_used")

                # Store notification status if present
                if result.get("notifications"):
                    status["notificationStatus"] = result.get("notifications")

                    # Create short notification summary for kubectl display
                    notifications = result.get("notifications")
                    notif_summary = []
                    if notifications:
                        for notif in notifications:
                            if notif.get("status") == "sent":
                                notif_summary.append(
                                    f"✓ {notif.get('type', 'unknown')}"
                                )
                            elif notif.get("status") == "failed":
                                notif_summary.append(
                                    f"✗ {notif.get('type', 'unknown')}"
                                )
                            elif notif.get("status") == "skipped":
                                notif_summary.append(
                                    f"- {notif.get('type', 'unknown')}"
                                )
                        status["notificationSummary"] = (
                            ", ".join(notif_summary) if notif_summary else ""
                        )

                # Create short summary for display (first 30 chars of message)
                msg = result.get("message", "")
                if len(msg) > 30:
                    status["shortMessage"] = msg[:27] + "..."
                else:
                    status["shortMessage"] = msg

                # Update conditions
                status["conditions"] = [
                    {
                        "type": "Complete",
                        "status": "True",
                        "lastTransitionTime": now,
                        "reason": result.get("status", "unknown"),
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
            # Format duration as human-readable string
            duration = result.get("duration", 0)
            history.insert(
                0,
                {
                    "executionTime": datetime.utcnow().isoformat() + "Z",
                    "result": result.get("status", "unknown"),
                    "duration": format_duration(duration) if duration else "0s",
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
                        "reason": result.get("status", "unknown"),
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

            # Update status to track active check
            self.add_active_check(name, namespace, check_name)

            # The HealthCheck will be handled by its own operator handlers
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
            # Parse and validate the cron schedule
            try:
                cron_trigger = CronTrigger.from_crontab(schedule)
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Invalid cron schedule '{schedule}' for {namespace}/{name}: {e}"
                )
                # Update status with error
                self.update_scheduled_status(
                    name,
                    namespace,
                    {
                        "status": "error",
                        "message": f"Invalid cron schedule: {str(e)}",
                        "error": str(e),
                    },
                    "unknown",
                )
                return job_id

            # Add the job to scheduler
            self.scheduler.add_job(
                self.execute_scheduled_check,
                cron_trigger,
                args=[name, namespace, spec],
                id=job_id,
                name=f"ScheduledHealthCheck: {namespace}/{name}",
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
                coalesce=True,  # Coalesce missed jobs
            )

            self.active_jobs[job_id] = f"{namespace}/{name}"
            scheduled_checks_active.set(len(self.active_jobs))
            checks_scheduled_total.labels(namespace=namespace, name=name).inc()
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
                scheduled_checks_active.set(len(self.active_jobs))
                logger.info(f"Unscheduled check: {namespace}/{name} (job: {job_id})")
            except Exception as e:
                logger.error(f"Failed to unschedule job {job_id}: {e}")

    def add_active_check(
        self, scheduled_name: str, namespace: str, check_name: str
    ) -> None:
        """
        Add a HealthCheck to the active list in ScheduledHealthCheck status.

        Args:
            scheduled_name: Name of the ScheduledHealthCheck
            namespace: Namespace of the resources
            check_name: Name of the created HealthCheck
        """
        try:
            # Load k8s config
            try:
                k8s_config.load_incluster_config()
            except Exception:
                k8s_config.load_kube_config()

            api = client.CustomObjectsApi()

            # Get current status
            try:
                current = api.get_namespaced_custom_object(
                    group="holmes.robusta.dev",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="scheduledhealthchecks",
                    name=scheduled_name,
                )
                current_status = current.get("status", {})
                active_checks = current_status.get("active", [])
            except Exception:
                active_checks = []

            # Get HealthCheck UID for tracking
            try:
                healthcheck = api.get_namespaced_custom_object(
                    group="holmes.robusta.dev",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="healthchecks",
                    name=check_name,
                )
                check_uid = healthcheck["metadata"]["uid"]

                # Only add to active list if we successfully got the UID
                active_checks.append(
                    {
                        "name": check_name,
                        "namespace": namespace,
                        "uid": check_uid,
                    }
                )
            except Exception as e:
                logger.warning(f"Could not get UID for HealthCheck {check_name}: {e}")
                # Don't add to active list if we can't get the HealthCheck
                return

            # Update status
            api.patch_namespaced_custom_object_status(
                group="holmes.robusta.dev",
                version="v1alpha1",
                namespace=namespace,
                plural="scheduledhealthchecks",
                name=scheduled_name,
                body={"status": {"active": active_checks}},
            )

            logger.debug(f"Added {check_name} to active checks for {scheduled_name}")

        except Exception as e:
            logger.error(f"Failed to update active checks for {scheduled_name}: {e}")

    def remove_active_check(
        self, scheduled_name: str, namespace: str, check_name: str
    ) -> None:
        """
        Remove a completed HealthCheck from the active list.

        Args:
            scheduled_name: Name of the ScheduledHealthCheck
            namespace: Namespace of the resources
            check_name: Name of the completed HealthCheck
        """
        try:
            # Load k8s config
            try:
                k8s_config.load_incluster_config()
            except Exception:
                k8s_config.load_kube_config()

            api = client.CustomObjectsApi()

            # Get current status
            try:
                current = api.get_namespaced_custom_object(
                    group="holmes.robusta.dev",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="scheduledhealthchecks",
                    name=scheduled_name,
                )
                current_status = current.get("status", {})
                active_checks = current_status.get("active", [])
            except Exception:
                return  # Nothing to remove

            # Remove from active list
            active_checks = [c for c in active_checks if c.get("name") != check_name]

            # Update status
            api.patch_namespaced_custom_object_status(
                group="holmes.robusta.dev",
                version="v1alpha1",
                namespace=namespace,
                plural="scheduledhealthchecks",
                name=scheduled_name,
                body={"status": {"active": active_checks}},
            )

            logger.debug(
                f"Removed {check_name} from active checks for {scheduled_name}"
            )

        except Exception as e:
            logger.error(f"Failed to remove active check for {scheduled_name}: {e}")

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
def handle_healthcheck_create(
    spec: Dict, name: str, namespace: str, labels: Dict, **kwargs
):
    """
    Handle HealthCheck creation - execute immediately.

    HealthChecks are one-time execution checks that run immediately when created.
    """
    logger.info(f"Handling HealthCheck creation: {namespace}/{name}")

    # Execute the check with status updates
    try:
        # Update status to Running
        operator.update_healthcheck_status(name, namespace, "Running", spec=spec)

        # Execute the check
        result = operator.execute_check(name, namespace, spec, is_one_time=True)

        # Update status based on result
        result_status = result.get("status", "error")
        final_phase = (
            "Passed"
            if result_status == "pass"
            else "Failed"
            if result_status == "fail"
            else "Error"
        )
        operator.update_healthcheck_status(name, namespace, final_phase, result, spec)
    except Exception as e:
        # If anything fails, ensure we update status to reflect the error
        logger.error(f"Error during HealthCheck execution for {namespace}/{name}: {e}")
        error_result = {
            "status": "error",
            "message": f"Check execution failed: {str(e)}",
            "error": str(e),
        }
        operator.update_healthcheck_status(name, namespace, "Error", error_result, spec)
        result = error_result  # Set result for use below

    # If this was created by a ScheduledHealthCheck, update its status
    scheduled_by = labels.get("holmes.robusta.dev/scheduled-by") if labels else None
    if scheduled_by:
        # Update the scheduled check's status with result
        operator.update_scheduled_status(scheduled_by, namespace, result, name)
        # Remove from active list
        operator.remove_active_check(scheduled_by, namespace, name)

    return {"executed": True, "result": result.get("status", "unknown")}


@kopf.on.update(
    "holmes.robusta.dev",
    "v1alpha1",
    "healthchecks",
    annotations={"holmes.robusta.dev/rerun": kopf.PRESENT},
)
def rerun_healthcheck_on_annotation(
    name: str, namespace: str, spec: Dict, labels: Dict, **kwargs
):
    """
    Re-run a HealthCheck when the rerun annotation is added.

    This allows re-executing a check by running:
    kubectl annotate healthcheck <name> holmes.robusta.dev/rerun=true --overwrite
    """
    logger.info(f"Re-running HealthCheck due to rerun annotation: {namespace}/{name}")

    # Remove the annotation first to prevent re-runs if execution fails
    try:
        api = client.CustomObjectsApi()
        api.patch_namespaced_custom_object(
            group="holmes.robusta.dev",
            version="v1alpha1",
            namespace=namespace,
            plural="healthchecks",
            name=name,
            body={"metadata": {"annotations": {"holmes.robusta.dev/rerun": None}}},
        )
    except Exception as e:
        logger.error(f"Failed to remove rerun annotation from {namespace}/{name}: {e}")

    # Execute the check with status updates
    try:
        # Update status to Running
        operator.update_healthcheck_status(name, namespace, "Running", spec=spec)

        # Execute the check
        result = operator.execute_check(name, namespace, spec, is_one_time=True)

        # Update status based on result
        result_status = result.get("status", "error")
        final_phase = (
            "Passed"
            if result_status == "pass"
            else "Failed"
            if result_status == "fail"
            else "Error"
        )
        operator.update_healthcheck_status(name, namespace, final_phase, result, spec)
    except Exception as e:
        # If anything fails, ensure we update status to reflect the error
        logger.error(f"Error during HealthCheck re-run for {namespace}/{name}: {e}")
        error_result = {
            "status": "error",
            "message": f"Check execution failed: {str(e)}",
            "error": str(e),
        }
        operator.update_healthcheck_status(name, namespace, "Error", error_result, spec)
        result = error_result

    # If this was created by a ScheduledHealthCheck, update its status
    scheduled_by = labels.get("holmes.robusta.dev/scheduled-by") if labels else None
    if scheduled_by:
        # Update the scheduled check's status with result
        operator.update_scheduled_status(scheduled_by, namespace, result, name)
        # Remove from active list
        operator.remove_active_check(scheduled_by, namespace, name)


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

    # Clean up from active_jobs to prevent memory leak
    check_identifier = f"{namespace}/{name}"
    jobs_to_clean = [
        job_id
        for job_id, check_name in operator.active_jobs.items()
        if check_name == check_identifier
    ]
    for job_id in jobs_to_clean:
        if job_id in operator.active_jobs:
            del operator.active_jobs[job_id]
    scheduled_checks_active.set(len(operator.active_jobs))


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

    # Remove the annotation first to prevent re-runs if execution fails
    try:
        api = client.CustomObjectsApi()
        api.patch_namespaced_custom_object(
            group="holmes.robusta.dev",
            version="v1alpha1",
            namespace=namespace,
            plural="scheduledhealthchecks",
            name=name,
            body={"metadata": {"annotations": {"holmes.robusta.dev/run-now": None}}},
        )
    except Exception as e:
        logger.error(
            f"Failed to remove run-now annotation from {namespace}/{name}: {e}"
        )

    # Now execute the check
    operator.execute_scheduled_check(name, namespace, spec)


if __name__ == "__main__":
    # Run the operator
    # In production, this would typically be run with:
    # kopf run -A --standalone operator.py
    import sys

    logger.info("Starting Holmes operator...")
    sys.exit(kopf.cli.main())
