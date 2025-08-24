#!/usr/bin/env python3
"""
Holmes Operator for Kubernetes

This operator manages HealthCheck CRDs and schedules their execution
by calling the Holmes API servers.
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp
import kopf
from apscheduler.schedulers.asyncio import AsyncIOScheduler
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
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        self.holmes_api_url = os.getenv("HOLMES_API_URL", "http://holmes-api:8080")
        self.session: Optional[aiohttp.ClientSession] = None

        # Track active jobs
        self.active_jobs: Dict[str, str] = {}  # job_id -> check_name

        logger.info(f"Holmes operator initialized with API URL: {self.holmes_api_url}")

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def execute_check(
        self, name: str, namespace: str, spec: Dict[str, Any]
    ) -> None:
        """
        Execute a health check by calling the Holmes API.

        Args:
            name: Name of the HealthCheck resource
            namespace: Namespace of the HealthCheck resource
            spec: Spec of the HealthCheck resource
        """
        check_identifier = f"{namespace}/{name}"
        logger.info(f"Executing check: {check_identifier}")

        session = await self.get_session()

        # Prepare the request
        check_request = {
            "query": spec["query"],
            "timeout": spec.get("timeout", 30),
            "mode": spec.get("mode", "monitor"),
            "destinations": spec.get("destinations", []),
        }

        try:
            # Call Holmes API
            async with session.post(
                f"{self.holmes_api_url}/api/check/execute",
                json=check_request,
                headers={"X-Check-Name": check_identifier},
                timeout=aiohttp.ClientTimeout(total=spec.get("timeout", 30) + 10),
            ) as response:
                result = await response.json()

                # Log the result
                logger.info(
                    f"Check {check_identifier} completed: {result.get('status', 'unknown')}"
                )

                # Update CRD status
                await self.update_status(name, namespace, result)

        except asyncio.TimeoutError:
            logger.error(f"Check {check_identifier} timed out")
            await self.update_status(
                name,
                namespace,
                {
                    "status": "error",
                    "message": "Check execution timed out",
                    "error": "TimeoutError",
                },
            )
        except Exception as e:
            logger.error(f"Error executing check {check_identifier}: {e}")
            await self.update_status(
                name,
                namespace,
                {
                    "status": "error",
                    "message": f"Check execution failed: {str(e)}",
                    "error": str(e),
                },
            )

    async def update_status(
        self, name: str, namespace: str, result: Dict[str, Any]
    ) -> None:
        """
        Update the HealthCheck CRD status with execution results.

        Args:
            name: Name of the HealthCheck resource
            namespace: Namespace of the HealthCheck resource
            result: Execution result from API
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
                    plural="healthchecks",
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
                },
            )
            history = history[:10]  # Keep only last 10 executions

            # Prepare status update
            now = datetime.utcnow().isoformat() + "Z"
            status = {
                "lastExecutionTime": now,
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
                plural="healthchecks",
                name=name,
                body={"status": status},
            )

            logger.debug(f"Updated status for {namespace}/{name}")

        except Exception as e:
            logger.error(f"Failed to update status for {namespace}/{name}: {e}")

    def schedule_check(self, name: str, namespace: str, spec: Dict[str, Any]) -> str:
        """
        Schedule a health check based on its spec.

        Args:
            name: Name of the HealthCheck resource
            namespace: Namespace of the HealthCheck resource
            spec: Spec of the HealthCheck resource

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
            logger.info(f"Check {namespace}/{name} is disabled, not scheduling")
            return job_id

        # Get schedule (default to every 5 minutes)
        schedule = spec.get("schedule", "*/5 * * * *")

        try:
            # Add the job to scheduler
            self.scheduler.add_job(
                self.execute_check,
                CronTrigger.from_crontab(schedule),
                args=[name, namespace, spec],
                id=job_id,
                name=f"HealthCheck: {namespace}/{name}",
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
            name: Name of the HealthCheck resource
            namespace: Namespace of the HealthCheck resource
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

    async def cleanup(self):
        """Clean up resources."""
        if self.session and not self.session.closed:
            await self.session.close()
        self.scheduler.shutdown()


# Create global operator instance
operator = HolmesCheckOperator()


@kopf.on.startup()
async def startup_handler(**kwargs):
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
async def cleanup_handler(**kwargs):
    """Clean up on shutdown."""
    logger.info("Holmes operator shutting down...")
    await operator.cleanup()


@kopf.on.create("holmes.robusta.dev", "v1alpha1", "healthchecks")
@kopf.on.update("holmes.robusta.dev", "v1alpha1", "healthchecks")
async def handle_healthcheck(spec: Dict, name: str, namespace: str, **kwargs):
    """
    Handle HealthCheck CRD create/update events.

    This is the main reconciliation loop for HealthCheck resources.
    """
    logger.info(f"Handling HealthCheck: {namespace}/{name}")

    # Schedule or reschedule the check
    job_id = operator.schedule_check(name, namespace, spec)

    # Return the job ID to store in the resource status
    return {"jobId": job_id}


@kopf.on.delete("holmes.robusta.dev", "v1alpha1", "healthchecks")
async def delete_healthcheck(name: str, namespace: str, **kwargs):
    """
    Handle HealthCheck deletion.

    Clean up any scheduled jobs for the deleted resource.
    """
    logger.info(f"Deleting HealthCheck: {namespace}/{name}")
    operator.unschedule_check(name, namespace)


@kopf.on.field("holmes.robusta.dev", "v1alpha1", "healthchecks", field="spec.enabled")
async def handle_enabled_change(
    old, new, name: str, namespace: str, spec: Dict, **kwargs
):
    """
    Handle changes to the enabled field.

    This allows users to enable/disable checks without deleting them.
    """
    if old is None:
        # Field was just added, use default behavior
        return

    if not new and old:
        # Check was disabled
        logger.info(f"Disabling HealthCheck: {namespace}/{name}")
        operator.unschedule_check(name, namespace)
    elif new and not old:
        # Check was enabled
        logger.info(f"Enabling HealthCheck: {namespace}/{name}")
        operator.schedule_check(name, namespace, spec)


# For testing purposes, allow running checks immediately
@kopf.on.annotation(
    "holmes.robusta.dev",
    "v1alpha1",
    "healthchecks",
    annotations={"holmes.robusta.dev/run-now": kopf.PRESENT},
)
async def run_check_now(name: str, namespace: str, spec: Dict, **kwargs):
    """
    Run a check immediately when the run-now annotation is added.

    This is useful for testing or forcing an immediate check execution.
    """
    logger.info(f"Running check immediately: {namespace}/{name}")
    await operator.execute_check(name, namespace, spec)

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


if __name__ == "__main__":
    # Run the operator
    # In production, this would typically be run with:
    # kopf run -A --standalone operator.py
    import sys

    logger.info("Starting Holmes operator...")
    sys.exit(kopf.cli.main())
