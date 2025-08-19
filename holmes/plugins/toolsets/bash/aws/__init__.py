import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.aws.constants import (
    SAFE_AWS_SERVICES,
    SAFE_AWS_OUTPUT_FORMATS,
    SAFE_AWS_GLOBAL_FLAGS,
    SAFE_AWS_SERVICE_FLAGS,
    BLOCKED_AWS_SERVICES,
    BLOCKED_AWS_OPERATIONS,
    SAFE_AWS_REGION_PATTERN,
)


def create_aws_parser(parent_parser: Any):
    """Create AWS CLI parser with safe command validation."""
    aws_parser = parent_parser.add_parser(
        "aws", help="Amazon Web Services Command Line Interface", exit_on_error=False
    )

    # Add service subparser
    aws_parser.add_argument(
        "service",
        type=validate_aws_service,
        help="AWS service name (e.g., ec2, s3, lambda)",
    )

    # Add operation/command
    aws_parser.add_argument("operation", help="AWS operation to perform")

    # Capture remaining arguments
    aws_parser.add_argument(
        "options",
        nargs=argparse.REMAINDER,
        default=[],
        help="Additional AWS CLI options and parameters",
    )


def validate_aws_service(service: str) -> str:
    """Validate that the AWS service is in the allowlist and not blocked."""
    if service in BLOCKED_AWS_SERVICES:
        raise argparse.ArgumentTypeError(
            f"AWS service '{service}' is not allowed for security reasons"
        )

    if service not in SAFE_AWS_SERVICES:
        allowed_services = ", ".join(sorted(SAFE_AWS_SERVICES.keys()))
        raise argparse.ArgumentTypeError(
            f"AWS service '{service}' is not in the allowlist. "
            f"Allowed services: {allowed_services}"
        )

    return service


def validate_aws_operation(service: str, operation: str) -> str:
    """Validate that the AWS operation is safe for the given service."""
    # Check if operation matches any blocked patterns
    for blocked_pattern in BLOCKED_AWS_OPERATIONS:
        if blocked_pattern.endswith("*"):
            prefix = blocked_pattern[:-1]
            if operation.startswith(prefix):
                raise ValueError(
                    f"AWS operation '{operation}' is blocked (matches pattern '{blocked_pattern}')"
                )
        elif operation == blocked_pattern:
            raise ValueError(f"AWS operation '{operation}' is blocked")

    # Check if operation is in the allowlist for this service
    allowed_operations = SAFE_AWS_SERVICES.get(service, set())
    if operation not in allowed_operations:
        allowed_ops_str = (
            ", ".join(sorted(allowed_operations)) if allowed_operations else "none"
        )
        raise ValueError(
            f"AWS operation '{operation}' is not allowed for service '{service}'. "
            f"Allowed operations: {allowed_ops_str}"
        )

    return operation


def validate_aws_options(options: list[str]) -> list[str]:
    """Validate AWS CLI options to ensure they are safe."""
    validated_options = []
    i = 0

    while i < len(options):
        option = options[i]

        # Handle flags that take values
        if option in {
            "--output",
            "--region",
            "--profile",
            "--query",
            "--endpoint-url",
            "--cli-read-timeout",
            "--cli-connect-timeout",
            "--page-size",
            "--max-items",
            "--starting-token",
            "--color",
            "--cli-binary-format",
        } or (
            option in SAFE_AWS_SERVICE_FLAGS
            and not option.startswith("--no-")
            and not option.startswith("--dry-run")
            and not option.startswith("--include-")
            and not option.startswith("--fetch-")
            and not option.startswith("--recursive")
            and not option.startswith("--with-decryption")
            and not option.startswith("--only-")
        ):
            if option == "--output":
                # Validate output format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                output_format = options[i + 1]
                if output_format not in SAFE_AWS_OUTPUT_FORMATS:
                    allowed_formats = ", ".join(sorted(SAFE_AWS_OUTPUT_FORMATS))
                    raise ValueError(
                        f"Output format '{output_format}' is not allowed. "
                        f"Allowed formats: {allowed_formats}"
                    )
                validated_options.extend([option, output_format])
                i += 2
                continue

            elif option == "--region":
                # Validate region format
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                region = options[i + 1]
                if not SAFE_AWS_REGION_PATTERN.match(region):
                    raise ValueError(f"Invalid AWS region format: {region}")
                validated_options.extend([option, region])
                i += 2
                continue

            elif option == "--query":
                # JMESPath queries are safe when properly quoted by shlex
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                query = options[i + 1]
                validated_options.extend([option, query])
                i += 2
                continue

            else:
                # For other options with values, add both
                if i + 1 >= len(options):
                    raise ValueError(f"Option {option} requires a value")
                validated_options.extend([option, options[i + 1]])
                i += 2
                continue

        # Handle boolean flags
        elif option in SAFE_AWS_GLOBAL_FLAGS or option in SAFE_AWS_SERVICE_FLAGS:
            validated_options.append(option)
            i += 1
            continue

        # Handle resource names and other parameters
        elif not option.startswith("--"):
            # Resource names and parameters - shlex will handle proper escaping
            validated_options.append(option)
            i += 1
            continue

        else:
            # Unknown option
            raise ValueError(f"Unknown or unsafe AWS CLI option: {option}")

    return validated_options


def validate_aws_command(cmd: Any) -> None:
    """
    Validate AWS command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    # Validate service (already done in parser, but double-check)
    if cmd.service in BLOCKED_AWS_SERVICES:
        raise ValueError(f"AWS service '{cmd.service}' is blocked")

    if cmd.service not in SAFE_AWS_SERVICES:
        raise ValueError(f"AWS service '{cmd.service}' is not allowed")

    # Validate operation
    validate_aws_operation(cmd.service, cmd.operation)

    # Validate options
    if hasattr(cmd, "options") and cmd.options:
        validate_aws_options(cmd.options)


def stringify_aws_command(
    command: Any, original_command: str, config: Optional[BashExecutorConfig]
) -> str:
    """Convert parsed AWS command back to safe command string."""
    if command.cmd != "aws":
        raise ValueError(f"Expected AWS command, got {command.cmd}")

    # Validate the command
    validate_aws_command(command)

    # Build command parts
    parts = ["aws", command.service, command.operation]

    # Add validated options
    if hasattr(command, "options") and command.options:
        validated_options = validate_aws_options(command.options)
        parts.extend(validated_options)

    return " ".join(escape_shell_args(parts))
