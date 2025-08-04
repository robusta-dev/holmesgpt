import subprocess
import time
from typing import List, Dict, Any, Optional
import signal
import os

from tests.llm.utils.test_case_utils import HolmesTestCase
from tests.llm.utils.setup_cleanup import log


class PortForward:
    """Manages a single port forward process."""

    def __init__(self, namespace: str, service: str, local_port: int, remote_port: int):
        self.namespace = namespace
        self.service = service
        self.local_port = local_port
        self.remote_port = remote_port
        self.process: Optional[subprocess.Popen] = None
        self.command = f"kubectl port-forward -n {namespace} svc/{service} {local_port}:{remote_port}"

    def start(self) -> None:
        """Start the port forward process."""
        try:
            log(
                f"🔌 Starting port forward: {self.service}:{self.remote_port} -> localhost:{self.local_port}"
            )

            # Check if port is already in use
            self._check_port_availability()

            # Start the process
            self.process = subprocess.Popen(
                self.command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                preexec_fn=os.setsid if os.name != "nt" else None,
            )

            # Give kubectl time to establish the port forward
            time.sleep(3)

            # Check if process is still running
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                error_msg = stderr if stderr else stdout

                # Check if it's a port conflict error
                if "address already in use" in error_msg.lower():
                    self._report_port_conflict()

                raise RuntimeError(f"Port forward failed to start: {error_msg}")

            log(
                f"✅ Port forward established: {self.service}:{self.remote_port} -> localhost:{self.local_port}"
            )
        except Exception as e:
            log(f"❌ Failed to start port forward: {e}")
            raise

    def _check_port_availability(self) -> None:
        """Check if the port is already in use and report what's using it."""
        if os.name != "nt":
            # On Unix-like systems, use lsof to find the process
            try:
                result = subprocess.run(
                    ["lsof", "-i", f":{self.local_port}"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    log(f"⚠️ Port {self.local_port} is already in use:")
                    log(result.stdout)
                    raise RuntimeError(
                        f"Port {self.local_port} is already in use. Please kill the existing process or use a different port."
                    )
            except Exception as e:
                # lsof might not be available, continue anyway
                log(f"⚠️ Could not check port availability: {e}")

    def _report_port_conflict(self) -> None:
        """Report detailed information about what's using the port."""
        try:
            if os.name != "nt":
                # Get detailed info about the process using the port
                result = subprocess.run(
                    ["lsof", "-i", f":{self.local_port}"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    log(f"\n📍 Port {self.local_port} is being used by:")
                    log(result.stdout)
                    log("\nTo fix this, either:")
                    log(
                        f"1. Kill the process using the port: kill $(lsof -ti :{self.local_port})"
                    )
                    log("2. Use a different port in your test configuration")
                    log("3. Wait for the process to finish and release the port\n")
        except Exception:
            pass

    def stop(self) -> None:
        """Stop the port forward process."""
        if self.process and self.process.poll() is None:
            try:
                if os.name != "nt":
                    # Kill the entire process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                else:
                    self.process.terminate()

                # Wait for process to terminate
                self.process.wait(timeout=5)
                log(f"🛑 Port forward stopped: {self.service}")
            except Exception as e:
                log(f"⚠️ Error stopping port forward: {e}")
                # Force kill if graceful termination fails
                try:
                    if os.name != "nt":
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    else:
                        self.process.kill()
                except Exception:
                    pass

    def __eq__(self, other):
        """Compare port forwards by their configuration."""
        if not isinstance(other, PortForward):
            return False
        return (
            self.namespace == other.namespace
            and self.service == other.service
            and self.local_port == other.local_port
            and self.remote_port == other.remote_port
        )

    def __hash__(self):
        """Hash based on configuration."""
        return hash((self.namespace, self.service, self.local_port, self.remote_port))


class PortForwardManager:
    """Manages multiple port forwards across all tests."""

    def __init__(self):
        self.port_forwards: List[PortForward] = []

    def add_port_forward(self, config: Dict[str, Any]) -> None:
        """Add a port forward configuration."""
        pf = PortForward(
            namespace=config["namespace"],
            service=config["service"],
            local_port=config["local_port"],
            remote_port=config["remote_port"],
        )
        # Only add if not already present
        if pf not in self.port_forwards:
            self.port_forwards.append(pf)

    def start_all(self) -> None:
        """Start all port forwards."""
        for pf in self.port_forwards:
            pf.start()

    def stop_all(self) -> None:
        """Stop all port forwards."""
        for pf in self.port_forwards:
            pf.stop()


def extract_port_forwards_from_test_cases(
    test_cases: List[HolmesTestCase],
) -> List[Dict[str, Any]]:
    """Extract unique port forward configurations from all test cases."""
    seen = set()
    unique_configs = []

    for test_case in test_cases:
        if test_case.port_forwards:
            for config in test_case.port_forwards:
                # Create a hashable key for deduplication
                key = (
                    config["namespace"],
                    config["service"],
                    config["local_port"],
                    config["remote_port"],
                )
                if key not in seen:
                    seen.add(key)
                    unique_configs.append(config)

    return unique_configs


def setup_all_port_forwards(test_cases: List[HolmesTestCase]) -> PortForwardManager:
    """Set up port forwards for all test cases that need them."""
    manager = PortForwardManager()

    # Extract all unique port forward configs
    all_configs = extract_port_forwards_from_test_cases(test_cases)

    if all_configs:
        log(f"\n🔌 Setting up {len(all_configs)} port forwards")
        for config in all_configs:
            manager.add_port_forward(config)

        # Start all port forwards
        manager.start_all()

    return manager


def cleanup_all_port_forwards(manager: PortForwardManager) -> None:
    """Clean up all port forwards."""
    if manager.port_forwards:
        log(f"\n🔌 Cleaning up {len(manager.port_forwards)} port forwards")
        manager.stop_all()
