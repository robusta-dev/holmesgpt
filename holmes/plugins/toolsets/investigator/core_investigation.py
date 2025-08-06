import logging
import os
from typing import Any, Dict

from holmes.core.tools import TodoWriteTool, Toolset, ToolsetTag, ToolsetStatusEnum


class CoreInvestigationToolset(Toolset):
    """Core toolset for investigation management and task planning."""

    def __init__(self):
        super().__init__(
            name="core_investigation",
            description="Core investigation tools for task management and planning",
            enabled=True,
            tools=[TodoWriteTool()],
            tags=[ToolsetTag.CORE],
            is_default=True,
        )
        # Override the default DISABLED status to ENABLED since this is a core toolset
        self.status = ToolsetStatusEnum.ENABLED
        logging.info("Core investigation toolset loaded")

    def get_example_config(self) -> Dict[str, Any]:
        return {}

    def _reload_instructions(self):
        """Load Datadog metrics specific troubleshooting instructions."""
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "investigator_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
