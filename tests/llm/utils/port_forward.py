import subprocess
import time
from typing import List, Dict, Any, Optional
import signal
import os
import re

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
        """Check if the port is already in use."""
        if _is_port_in_use(self.local_port):
            self._report_port_conflict()
            raise RuntimeError(
                f"Port {self.local_port} is already in use. Please kill the existing process or use a different port."
            )

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
        self.failed_port_forwards: Dict[int, str] = {}  # port -> error message

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

    def start_all(self) -> Dict[int, str]:
        """Start all port forwards, continue even if some fail.

        Returns:
            Dict mapping port numbers to error messages for failed port forwards.
        """
        for pf in self.port_forwards:
            try:
                pf.start()
            except Exception as e:
                error_msg = str(e)
                self.failed_port_forwards[pf.local_port] = error_msg
                log(
                    f"⚠️ Port forward failed for port {pf.local_port}, tests requiring this will be skipped: {error_msg}"
                )

        return self.failed_port_forwards

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


def check_port_availability_early(test_cases: List[HolmesTestCase]) -> None:
    """Check for port conflicts and availability before running any setup scripts."""
    port_usage: Dict[int, List[str]] = {}

    # Collect all port usages
    for test_case in test_cases:
        if test_case.port_forwards:
            for config in test_case.port_forwards:
                local_port = config["local_port"]
                test_id = test_case.id

                if local_port not in port_usage:
                    port_usage[local_port] = []
                port_usage[local_port].append(test_id)

    # Check for conflicts between tests
    conflicts = []
    for port, test_ids in port_usage.items():
        if len(test_ids) > 1:
            # Check if all test_ids are variants of the same test (e.g., test[0], test[1])
            # Extract base test name by removing variant suffix [0], [1], etc.
            base_names = set()
            for tid in test_ids:
                # Remove variant suffix if present
                base_name = re.sub(r"\[\d+\]$", "", tid)
                base_names.add(base_name)

            # Only report as conflict if they're different base tests
            if len(base_names) > 1:
                conflicts.append((port, test_ids))

    if conflicts:
        error_msg = "\n🚨 Port conflicts detected! Multiple tests are trying to use the same local port:\n"
        for port, test_ids in conflicts:
            error_msg += f"\n  Port {port} is used by tests: {', '.join(test_ids)}"

        error_msg += "\n\nTo fix this:"
        error_msg += (
            "\n  1. Update the test_case.yaml files to use different local_port values"
        )
        error_msg += "\n  2. Ensure each test uses a unique local port"
        error_msg += "\n  3. Consider using the test number as part of the port (e.g., test 148 → port 3148)"
        error_msg += "\n\nAlternatively, you can skip all tests requiring port forwards by running:"
        error_msg += "\n  pytest -m 'not port-forward'"

        log(error_msg)
        raise RuntimeError(
            "Port conflicts detected. Please fix the conflicts before running tests."
        )

    # Check if ports are already in use on the system
    ports_in_use = []
    for port in port_usage.keys():
        if _is_port_in_use(port):
            ports_in_use.append(port)

    if ports_in_use:
        error_msg = "\n🚨 Ports already in use on the system:\n"
        for port in ports_in_use:
            error_msg += f"\n  Port {port} is already in use (required by tests: {', '.join(port_usage[port])})"

        error_msg += "\n\nTo see what's using these ports:"
        error_msg += f"\n  lsof -i :{','.join(str(p) for p in ports_in_use)}"
        error_msg += "\n\nTo fix this:"
        error_msg += "\n  1. Kill the processes using these ports"
        error_msg += "\n  2. Or skip port-forward tests: pytest -m 'not port-forward'"

        log(error_msg)
        raise RuntimeError("Required ports are already in use.")


def _is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Try to bind to the port
        sock.bind(("localhost", port))
        return False  # Port is available
    except OSError:
        return True  # Port is in use
    finally:
        sock.close()


def setup_all_port_forwards(
    test_cases: List[HolmesTestCase],
) -> tuple[PortForwardManager, Dict[str, str]]:
    """Set up port forwards for all test cases that need them.

    Returns:
        Tuple of (manager, port_forward_failures) where port_forward_failures maps
        test IDs to error messages for tests whose port forwards failed.
    """
    manager = PortForwardManager()
    test_port_forward_failures: Dict[str, str] = {}

    # Extract all unique port forward configs
    all_configs = extract_port_forwards_from_test_cases(test_cases)

    if all_configs:
        log(f"\n🔌 Setting up {len(all_configs)} port forwards")
        for config in all_configs:
            manager.add_port_forward(config)

        # Start all port forwards (will continue even if some fail)
        failed_ports = manager.start_all()

        # Map failed ports back to test IDs
        if failed_ports:
            for test_case in test_cases:
                if test_case.port_forwards:
                    for pf_config in test_case.port_forwards:
                        if pf_config["local_port"] in failed_ports:
                            test_port_forward_failures[test_case.id] = (
                                f"Port forward failed for port {pf_config['local_port']}: "
                                f"{failed_ports[pf_config['local_port']]}"
                            )
                            break  # One failed port forward is enough to skip the test

    return manager, test_port_forward_failures


def cleanup_port_forwards_by_config(configs: List[Dict[str, Any]]) -> None:
    """Clean up port forwards by killing kubectl processes matching the configs.

    This approach is used instead of cleanup_all_port_forwards because with xdist
    the worker that created the port forwards may not be the one cleaning them up.
    (We can't use the same worker to clean up because other tests might still be running -
    we need to cleanup on the last worker only.)

    This is more "violent" than using the PortForwardManager's stop() method, but it's
    unfortunately necessary. An alternative is to do setup/cleanu on master worker,
    but I'm not sure how to do that with xdist.
    """
    if not configs:
        return

    log(f"\n🔌 Cleaning up {len(configs)} port forwards")

    for config in configs:
        try:
            # Find and kill kubectl port-forward processes for this specific port
            local_port = config["local_port"]

            if os.name != "nt":
                # On Unix-like systems, find the process using the port
                result = subprocess.run(
                    ["lsof", "-ti", f":{local_port}"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split("\n")
                    for pid in pids:
                        try:
                            # Check if it's a kubectl process before killing
                            ps_result = subprocess.run(
                                ["ps", "-p", pid, "-o", "comm="],
                                capture_output=True,
                                text=True,
                            )
                            if (
                                ps_result.returncode == 0
                                and "kubectl" in ps_result.stdout
                            ):
                                os.kill(int(pid), signal.SIGTERM)
                                log(
                                    f"🛑 Killed kubectl port-forward on port {local_port} (PID: {pid})"
                                )
                        except (ValueError, ProcessLookupError):
                            pass
        except Exception as e:
            log(f"⚠️ Error cleaning up port forward on port {config['local_port']}: {e}")
