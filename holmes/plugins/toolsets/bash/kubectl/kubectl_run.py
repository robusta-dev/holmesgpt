import re
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import (
    BashExecutorConfig,
    KubectlImageConfig,
)
from holmes.plugins.toolsets.bash.common.stringify import escape_shell_args
from holmes.plugins.toolsets.bash.common.validators import regex_validator
from holmes.plugins.toolsets.bash.kubectl.constants import (
    SAFE_NAME_PATTERN,
    SAFE_NAMESPACE_PATTERN,
)

# Pattern for validating Docker image names
SAFE_IMAGE_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_./:]*$")

# Pattern for validating command arguments (alphanumeric, common symbols, spaces)
SAFE_COMMAND_PATTERN = re.compile(r"^[a-zA-Z0-9\-_./:\s=<>]*$")


def simplify_kubectl_run_for_argparse(cmd: str):
    """The argparse parser does not work well with kubectl commands that use double dash `--` to separate the container's command from the kubectl options.
    This method hacks the command and simplifies it for argparse
    """
    if cmd.startswith("kubectl run") and " --command -- " in cmd:
        replaced = cmd.replace(" --command -- ", " --command ")
        return replaced

    return cmd


def validate_image_and_commands(
    image: str, container_command: str, config: Optional[BashExecutorConfig]
) -> None:
    """
    Validate that the image is in the whitelist and commands are allowed.
    Raises ArgumentTypeError if validation fails.
    """
    if not config or not config.kubectl or not config.kubectl.allowed_images:
        raise ValueError(
            "The command `kubectl run` is not allowed. The user must whitelist specific images and commands but none have been configured."
        )

    # Find matching image config
    image_config: Optional[KubectlImageConfig] = None
    for img_config in config.kubectl.allowed_images:
        if img_config.image == image:
            image_config = img_config
            break

    if not image_config:
        allowed_images = [img.image for img in config.kubectl.allowed_images]
        raise ValueError(
            f"Image '{image}' not allowed. Allowed images: {', '.join(allowed_images)}"
        )

    # Validate commands against allowed patterns
    command_allowed = False
    for allowed_pattern in image_config.allowed_commands:
        if re.match(allowed_pattern, container_command):
            command_allowed = True
            break

    if not command_allowed:
        raise ValueError(
            f"Command '{container_command}' not allowed for image '{image}'. "
            f"Allowed patterns: {', '.join(image_config.allowed_commands)}"
        )


def create_kubectl_run_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser("run", exit_on_error=False)

    parser.add_argument(
        "name",
        type=regex_validator("pod name", SAFE_NAME_PATTERN),
    )

    parser.add_argument(
        "--image",
        required=True,
        type=regex_validator("image", SAFE_IMAGE_PATTERN),
    )

    parser.add_argument(
        "-n",
        "--namespace",
        type=regex_validator("namespace", SAFE_NAMESPACE_PATTERN),
    )

    parser.add_argument(
        "--rm", action="store_true", help="Delete resources created in this command"
    )

    parser.add_argument("--attach", action="store_true", help="Attach to the container")

    parser.add_argument(
        "--restart",
        choices=["Never"],
        default="Never",
    )

    parser.add_argument(
        "--overrides",
    )

    parser.add_argument("--command", nargs="+")


def stringify_run_command(cmd: Any, config: Optional[BashExecutorConfig]) -> str:
    # Validate image and commands if configured
    if cmd.image and cmd.command:
        container_command = " ".join(cmd.command)
        validate_image_and_commands(
            image=cmd.image, container_command=container_command, config=config
        )

    parts = ["kubectl", "run", cmd.name]

    if cmd.overrides:
        raise ValueError(
            "--override is not an accepted argument. It has been disabled for security reasons"
        )

    if cmd.image:
        parts.extend(["--image", cmd.image])

    if cmd.namespace:
        parts.extend(["--namespace", cmd.namespace])

    if cmd.rm:
        parts.append("--rm")

    if cmd.attach:
        parts.append("--attach")

    if cmd.restart:
        parts.extend(["--restart", cmd.restart])

    if cmd.command:
        parts.append("--command")
        parts.append("--")
        parts.extend(cmd.command)

    return " ".join(escape_shell_args(parts))
