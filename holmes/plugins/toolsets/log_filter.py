import logging
import os
from typing import Any, Dict, Tuple

import requests  # type: ignore
import yaml
from pydantic import BaseModel

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    Tool,
    ToolParameter,
    ToolResultStatus,
    Toolset,
    ToolsetTag,
)

"""
Example of the content of the log filter config file:
```yaml
log_filter:
  - label: k8s-app=kube-dns
    filters:
      - "[WARNING] No files matching import glob pattern"
```
"""
LOG_FILTER_CONFIG_PATH = "LOG_FILTER"


class LogFilter(BaseModel):
    label: str
    filters: list[str]


class LogFilterConfig(BaseModel):
    log_filter: list[LogFilter]


class LogFilterToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="log_filter",
            enabled=True,
            description="A toolset to return a pod log filter based on pod labels.",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/log_filter.html",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Filter_icon.svg/1200px-Filter_icon.svg.png",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[LogFilterTool()],
            tags=[ToolsetTag.CLI],
            is_default=True,
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        log_filter_config_path = os.environ.get(LOG_FILTER_CONFIG_PATH, None)
        if not log_filter_config_path:
            return True, ""

        try:
            log_filter_str = load_log_filter_config(log_filter_config_path)
            log_filter = yaml.safe_load(log_filter_str)
            LogFilterConfig.model_validate(log_filter)
        except Exception as e:
            return (
                False,
                f"Log filter config from {log_filter_config_path} is not valid: {str(e)}",
            )
        return True, ""

    def get_example_config(self) -> Dict[str, Any]:
        return {}


class LogFilterTool(Tool):
    def __init__(self):
        super().__init__(
            name="log_filter",
            description="Return logs filter Perl-based regular expression based on the pod label.",
            parameters={
                "label": ToolParameter(
                    type="string",
                    description="The pod label to filter logs by. For example, 'app=my-app'.",
                ),
            },
        )

    def get_parameterized_one_liner(self, params) -> str:
        return f"logs filter for pod label {params.get('label')}"

    @staticmethod
    def get_default_log_filter(params: dict) -> StructuredToolResult:
        """Returns a default log filter regex pattern filter out info level log"""
        default_log_filter = "(^I\d{4})|(level=info)"
        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data=default_log_filter,
            params=params,
        )

    @staticmethod
    def label_in_labels(key_value: str, log_filter: str) -> bool:
        """Check if a key=value string is in a list of labels joined by comma."""
        label_list = log_filter.split(",")
        return any(item == key_value for item in label_list)

    def _invoke(self, params: Dict[str, Any]) -> StructuredToolResult:
        # _invoke returns default log filter if no matching label is found

        log_filter_config_path = os.environ.get(LOG_FILTER_CONFIG_PATH, None)
        if not log_filter_config_path:
            return self.get_default_log_filter(params)

        if params.get("label") is None:
            logging.info("label is not provided. Returning default log filter.")
            return self.get_default_log_filter(params)

        try:
            log_filter_str = load_log_filter_config(log_filter_config_path)
            log_filter_dict = yaml.safe_load(log_filter_str)

            log_filters = LogFilterConfig(**log_filter_dict)

            for log_filter in log_filters.log_filter:
                if self.label_in_labels(params["label"], log_filter.label):
                    combined_filter = "|".join(log_filter.filters)
                    return StructuredToolResult(
                        status=ToolResultStatus.SUCCESS,
                        data=f"({combined_filter})",
                        params=params,
                    )
            logging.info(
                f"label '{params['label']}' not found in log filter config. Returning default log filter."
            )
        except Exception as e:
            logging.error(
                f"Error processing log filter config: {str(e)}. Returning default log filter."
            )
        return self.get_default_log_filter(params)


def load_log_filter_config(file_path: str) -> str:
    """Reads a file, either local or remote.

    Args:
        file_path: The path to the file, can be a local path or a URL.

    Returns:
        The content of the file as a string, or None if an error occurs.
    """
    if file_path.startswith("http://") or file_path.startswith("https://"):
        # Handle remote file (URL)
        response = requests.get(file_path)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.text
    # Handle local file
    if os.path.exists(file_path) and os.path.isfile(file_path):
        with open(file_path, "r") as file:
            return file.read()
    raise FileNotFoundError(f"File not found: {file_path}")
