import argparse
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.bash_command import BashCommand
from holmes.plugins.toolsets.bash.common.config import BashExecutorConfig
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.aws.constants import (
    SAFE_AWS_SERVICES,
    BLOCKED_AWS_SERVICES,
    BLOCKED_AWS_OPERATIONS,
)


class AWSCommand(BashCommand):
    def __init__(self):
        super().__init__("aws")

    def add_parser(self, parent_parser: Any):
        """Create AWS CLI parser with safe command validation."""
        aws_parser = parent_parser.add_parser(
            "aws",
            help="Amazon Web Services Command Line Interface",
            exit_on_error=False,
        )

        aws_parser.add_argument(
            "service",
            type=validate_aws_service,
            help="AWS service name (e.g., ec2, s3, lambda)",
        )

        aws_parser.add_argument("operation", help="AWS operation to perform")

        aws_parser.add_argument(
            "options",
            nargs=argparse.REMAINDER,
            default=[],
            help="Additional AWS CLI options and parameters",
        )
        return aws_parser

    def validate_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> None:
        validate_aws_command(command)

    def stringify_command(
        self, command: Any, original_command: str, config: Optional[BashExecutorConfig]
    ) -> str:
        """Convert parsed AWS command back to safe command string."""
        parts = ["aws", command.service, command.operation]

        if hasattr(command, "options") and command.options:
            parts.extend(command.options)

        return " ".join(escape_shell_args(parts))


# Keep old functions for backward compatibility temporarily
def create_aws_parser(parent_parser: Any):
    aws_command = AWSCommand()
    return aws_command.add_parser(parent_parser)


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


def validate_aws_command(cmd: Any) -> None:
    """
    Validate AWS command to prevent injection attacks and ensure safety.
    Raises ValueError if validation fails.
    """
    if cmd.service in BLOCKED_AWS_SERVICES:
        raise ValueError(f"AWS service '{cmd.service}' is blocked")

    if cmd.service not in SAFE_AWS_SERVICES:
        raise ValueError(f"AWS service '{cmd.service}' is not allowed")

    validate_aws_operation(cmd.service, cmd.operation)
