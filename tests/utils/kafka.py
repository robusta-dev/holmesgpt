
import shutil
import subprocess
import time
from typing import Tuple
from confluent_kafka.admin import AdminClient


import socket
import json
def docker_not_available() -> Tuple[bool, str]:
    """
    Check if docker command is available in the system.
    Returns a tuple of (skip_test: bool, reason: str)
    """
    # First check if docker command exists in PATH
    if not shutil.which('docker'):
        return True, "Docker command not found in PATH"

    try:
        # Try to run 'docker info' to check if docker daemon is running
        subprocess.run(
            ['docker', 'info'],
            check=True,
            capture_output=True,
            timeout=5  # 5 seconds timeout
        )
        return False, ""
    except subprocess.CalledProcessError:
        return True, "Docker daemon not running"
    except subprocess.TimeoutExpired:
        return True, "Docker command timed out"
    except Exception as e:
        return True, f"Docker not available: {str(e)}"

def wait_for_containers(folder):
    max_attempts = 300
    attempt = 0
    while attempt < max_attempts:
        try:
            result = subprocess.run(
                "docker compose ps --format json".split(),
                cwd=folder,
                capture_output=True,
                text=True
            )

            ps = json.loads(result.stdout)

            if ps.get("State") == "running" and ps.get("Health") == "healthy":
                return True
        except Exception:
            pass
        attempt += 1
        time.sleep(1)
    return False

def wait_for_kafka_ready(client:AdminClient, max_retries=30, delay=2):
    for i in range(max_retries):
        try:
            # Try to list topics (this will fail if Kafka isn't ready)
            client.list_topics()
            return True
        except Exception:
            print(f"Waiting for Kafka to be ready... ({i+1}/{max_retries})")
            time.sleep(delay)
    return False