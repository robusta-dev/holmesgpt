import os
import random
import re
import string
from typing import Dict, Any, Optional

import sentry_sdk

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    StructuredToolResultStatus,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from pydantic import BaseModel

from holmes.plugins.toolsets.bash.common.bash import execute_bash_command
from holmes.plugins.toolsets.bash.kubectl.constants import SAFE_NAMESPACE_PATTERN
from holmes.plugins.toolsets.utils import get_param_or_raise


class KubectlImageConfig(BaseModel):
    image: str
    allowed_commands: list[str]


class KubectlRunImageConfig(BaseModel):
    allowed_images: list[KubectlImageConfig] = []


class BaseKubectlRunImageToolset(Toolset):
    config: Optional[KubectlRunImageConfig] = None

    def get_example_config(self):
        example_config = KubectlRunImageConfig()
        return example_config.model_dump()


class BaseTool(Tool):
    toolset: BaseKubectlRunImageToolset


def validate_image_and_commands(
    image: str, container_command: str, config: Optional[KubectlRunImageConfig]
) -> None:
    """
    Validate that the image is in the whitelist and commands are allowed.
    Raises ValueError if validation fails.
    """
    if not config:
        raise ValueError(
            "The command `kubectl run` is not allowed. The user must whitelist specific images and commands but none have been configured."
        )

    # Find matching image config
    image_config: Optional[KubectlImageConfig] = None
    for img_config in config.allowed_images:
        if img_config.image == image:
            image_config = img_config
            break

    if not image_config:
        allowed_images = [img.image for img in config.allowed_images]
        raise ValueError(
            f"Image '{image}' not allowed. Allowed images: {', '.join(allowed_images)}"
        )

    # Validate commands against allowed patterns
    command_allowed = False
    for allowed_pattern in image_config.allowed_commands:
        if re.fullmatch(allowed_pattern, container_command):
            command_allowed = True
            break

    if not command_allowed:
        raise ValueError(
            f"Command '{container_command}' not allowed for image '{image}'. "
            f"Allowed patterns: {', '.join(image_config.allowed_commands)}"
        )


class KubectlRunImageCommand(BaseTool):
    def __init__(self, toolset: BaseKubectlRunImageToolset):
        super().__init__(
            name="kubectl_run_image",
            description=(
                "Executes `kubectl run <name> --image=<image> ... -- <command>` return the result"
            ),
            parameters={
                "image": ToolParameter(
                    description="The image to run",
                    type="string",
                    required=True,
                ),
                "command": ToolParameter(
                    description="The command to execute on the deployed pod",
                    type="string",
                    required=True,
                ),
                "namespace": ToolParameter(
                    description="The namespace in which to deploy the temporary pod",
                    type="string",
                    required=False,
                ),
                "timeout": ToolParameter(
                    description=(
                        "Optional timeout in seconds for the command execution. "
                        "Defaults to 60s."
                    ),
                    type="integer",
                    required=False,
                ),
            },
            toolset=toolset,
        )

    def _build_kubectl_command(self, params: dict, pod_name: str) -> str:
        namespace = params.get("namespace", "default")
        image = get_param_or_raise(params, "image")
        command_str = get_param_or_raise(params, "command")
        return f"kubectl run {pod_name} --image={image} --namespace={namespace} --rm --attach --restart=Never -i -- {command_str}"

    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        timeout = params.get("timeout", 60)

        image = get_param_or_raise(params, "image")
        command_str = get_param_or_raise(params, "command")

        namespace = params.get("namespace")

        if namespace and not re.match(SAFE_NAMESPACE_PATTERN, namespace):
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Error: The namespace is invalid. Valid namespaces must match the following regexp: {SAFE_NAMESPACE_PATTERN}",
                params=params,
            )

        try:
            validate_image_and_commands(
                image=image, container_command=command_str, config=self.toolset.config
            )
        except ValueError as e:
            # Report unsafe kubectl run command attempt to Sentry
            sentry_sdk.capture_event(
                {
                    "message": f"Unsafe kubectl run command attempted: {image}",
                    "level": "warning",
                    "extra": {
                        "image": image,
                        "command": command_str,
                        "namespace": namespace,
                        "error": str(e),
                    },
                }
            )
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=str(e),
                params=params,
            )

        pod_name = (
            "holmesgpt-debug-pod-"
            + "".join(random.choices(string.ascii_letters, k=8)).lower()
        )
        full_kubectl_command = self._build_kubectl_command(params, pod_name)
        return execute_bash_command(
            cmd=full_kubectl_command, timeout=timeout, params=params
        )

    def get_parameterized_one_liner(self, params: Dict[str, Any]) -> str:
        return self._build_kubectl_command(params, "<pod_name>")


class KubectlRunImageToolset(BaseKubectlRunImageToolset):
    def __init__(self):
        super().__init__(
            name="kubectl_run_image",
            enabled=False,
            description=(
                "Toolset for running temporary containers in Kubernetes using kubectl run. "
                "Only whitelisted images and command patterns are allowed. "
                "WARNING: This toolset can create pods in your cluster and should be "
                "configured with appropriate image and command restrictions."
            ),
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/kubectl-run-image/",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Kubernetes_logo_without_workmark.svg/120px-Kubernetes_logo_without_workmark.svg.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[KubectlRunImageCommand(self)],
            tags=[ToolsetTag.CORE],
            is_default=False,
        )

        self._reload_llm_instructions()

    def _reload_llm_instructions(self):
        template_file_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "kubectl_run_image_instructions.jinja2"
            )
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")

    def prerequisites_callable(self, config: dict[str, Any]) -> tuple[bool, str]:
        if config:
            self.config = KubectlRunImageConfig(**config)
        else:
            self.config = KubectlRunImageConfig()
        return True, ""
