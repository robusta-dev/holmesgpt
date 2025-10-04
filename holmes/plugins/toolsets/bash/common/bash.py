import subprocess
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus


def execute_bash_command(cmd: str, timeout: int, params: dict) -> StructuredToolResult:
    try:
        process = subprocess.run(
            cmd,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )

        stdout = process.stdout.strip() if process.stdout else ""
        result_data = f"{cmd}\n" f"{stdout}"

        status = StructuredToolResultStatus.ERROR
        if process.returncode == 0 and stdout:
            status = StructuredToolResultStatus.SUCCESS
        elif not stdout:
            status = StructuredToolResultStatus.NO_DATA

        return StructuredToolResult(
            status=status,
            data=result_data,
            params=params,
            invocation=cmd,
            return_code=process.returncode,
        )
    except subprocess.TimeoutExpired:
        return StructuredToolResult(
            status=StructuredToolResultStatus.ERROR,
            error=f"Error: Command '{cmd}' timed out after {timeout} seconds.",
            params=params,
        )
    except FileNotFoundError:
        # This might occur if /bin/bash is not found, or if shell=False and command is not found
        return StructuredToolResult(
            status=StructuredToolResultStatus.ERROR,
            error="Error: Bash executable or command not found. Ensure bash is installed and the command is valid.",
            params=params,
        )
    except Exception as e:
        return StructuredToolResult(
            status=StructuredToolResultStatus.ERROR,
            error=f"Error executing command '{cmd}': {str(e)}",
            params=params,
        )
