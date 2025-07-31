import logging
from typing import List, Optional

import sentry_sdk

from holmes.core.tools import (
    StructuredToolResult,
    Tool,
    ToolResultStatus,
    Toolset,
    ToolsetStatusEnum,
)
from holmes.core.tools_utils.toolset_utils import filter_out_default_logging_toolset


class ToolExecutor:
    def __init__(self, toolsets: List[Toolset]):
        # TODO: expose function for this instead of callers accessing directly
        self.toolsets = toolsets

        enabled_toolsets: list[Toolset] = list(
            filter(
                lambda toolset: toolset.status == ToolsetStatusEnum.ENABLED,
                toolsets,
            )
        )

        self.enabled_toolsets: list[Toolset] = filter_out_default_logging_toolset(
            enabled_toolsets
        )

        toolsets_by_name: dict[str, Toolset] = {}
        for ts in self.enabled_toolsets:
            if ts.name in toolsets_by_name:
                logging.warning(f"Overriding toolset '{ts.name}'!")
            toolsets_by_name[ts.name] = ts

        self.tools_by_name: dict[str, Tool] = {}
        for ts in toolsets_by_name.values():
            for tool in ts.tools:
                if tool.name in self.tools_by_name:
                    logging.warning(
                        f"Overriding existing tool '{tool.name} with new tool from {ts.name} at {ts.path}'!"
                    )
                self.tools_by_name[tool.name] = tool

        # Debug info
        if "update_hypotheses" in self.tools_by_name:
            logging.info("✓ update_hypotheses tool is available in tool executor")
        else:
            logging.warning("✗ update_hypotheses tool NOT found in tool executor")

    def invoke(self, tool_name: str, params: dict) -> StructuredToolResult:
        tool = self.get_tool_by_name(tool_name)
        return (
            tool.invoke(params)
            if tool
            else StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Could not find tool named {tool_name}",
            )
        )

    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        if name in self.tools_by_name:
            return self.tools_by_name[name]
        logging.warning(f"could not find tool {name}. skipping")
        return None

    @sentry_sdk.trace
    def get_all_tools_openai_format(self):
        return [tool.get_openai_format() for tool in self.tools_by_name.values()]

    def get_context_reminders(self) -> List[str]:
        """
        Collect context reminders from all enabled tools that want to inject context.

        Returns:
            List of reminder strings from tools that have context to share
        """
        reminders = []
        for tool in self.tools_by_name.values():
            reminder = tool.get_context_reminder()
            if reminder:
                reminders.append(reminder)
        return reminders
