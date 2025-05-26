import argparse
import re
from typing import Any, Optional

from holmes.plugins.toolsets.bash.common.config import KubectlImageConfig
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


def validate_image_and_commands(image: str, commands: list[str], config) -> None:
    """
    Validate that the image is in the whitelist and commands are allowed.
    Raises ArgumentTypeError if validation fails.
    """
    if not config or not config.kubectl or not config.kubectl.allowed_images:
        raise argparse.ArgumentTypeError(
            "No image configuration found. Image validation required for kubectl run but the user has not allowed any image to be run. Either suggest for the user to add an image or run the command themselves."
        )

    # Find matching image config
    image_config: Optional[KubectlImageConfig] = None
    for img_config in config.kubectl.allowed_images:
        if img_config.image == image:
            image_config = img_config
            break

    if not image_config:
        allowed_images = [img.image for img in config.kubectl.allowed_images]
        raise argparse.ArgumentTypeError(
            f"Image '{image}' not allowed. Allowed images: {', '.join(allowed_images)}"
        )

    # Validate commands against allowed patterns
    for command in commands:
        command_allowed = False
        for allowed_pattern in image_config.allowed_commands:
            if re.match(allowed_pattern, command):
                command_allowed = True
                break

        if not command_allowed:
            raise argparse.ArgumentTypeError(
                f"Command '{command}' not allowed for image '{image}'. "
                f"Allowed patterns: {', '.join(image_config.allowed_commands)}"
            )


def create_kubectl_run_parser(kubectl_parser: Any):
    parser = kubectl_parser.add_parser(
        "run", help="Run a particular image on the cluster", exit_on_error=False
    )

    parser.add_argument(
        "name",
        type=regex_validator("pod name", SAFE_NAME_PATTERN),
        help="Name of the pod to create",
    )

    parser.add_argument(
        "--image",
        required=True,
        type=regex_validator("image", SAFE_IMAGE_PATTERN),
        help="The image for the container to run",
    )

    parser.add_argument(
        "-n",
        "--namespace",
        type=regex_validator("namespace", SAFE_NAMESPACE_PATTERN),
        help="Namespace to create the pod in",
    )

    parser.add_argument(
        "--rm", action="store_true", help="Delete resources created in this command"
    )

    parser.add_argument("--attach", action="store_true", help="Attach to the container")

    parser.add_argument(
        "--restart",
        choices=["Always", "OnFailure", "Never"],
        default="Always",
        help="Restart policy for the pod",
    )

    parser.add_argument(
        "--command",
        action="store_true",
        help="If true, use -- to separate the command from the image",
    )

    parser.add_argument(
        "command_args", nargs="*", help="Command and arguments to run in the container"
    )


def stringify_run_command(cmd: Any, config=None) -> str:
    # Validate image and commands if configured
    if cmd.image and cmd.command_args:
        validate_image_and_commands(cmd.image, cmd.command_args, config)

    parts = ["kubectl", "run", cmd.name]

    if cmd.image:
        parts.extend(["--image", cmd.image])

    if cmd.namespace:
        parts.extend(["--namespace", cmd.namespace])

    if cmd.rm:
        parts.append("--rm")

    if cmd.attach:
        parts.append("--attach")

    if cmd.restart and cmd.restart != "Always":
        parts.extend(["--restart", cmd.restart])

    if cmd.command:
        parts.append("--command")
        if cmd.command_args:
            parts.append("--")
            # Validate command args using safe pattern
            for arg in cmd.command_args:
                if not SAFE_COMMAND_PATTERN.match(arg):
                    raise argparse.ArgumentTypeError(f"Unsafe command argument: {arg}")
            parts.extend(cmd.command_args)

    return " ".join(escape_shell_args(parts))
