import logging
import os
from typing import Any, Dict
from uuid import uuid4

from holmes.core.todo_tasks_formatter import format_tasks
from holmes.core.tools import (
    StructuredToolResult,
    StructuredToolResultStatus,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from holmes.plugins.toolsets.investigator.model import Task, TaskStatus
from holmes.plugins.toolsets.utils import toolset_name_for_one_liner


class PplQueryAssistTool(Tool):
    name: str = "opensearch_ppl_query_assist"
    description: str = "Generate valid OpenSearch Piped Processing Language (PPL) queries to suggest to users for execution"
    parameters: Dict[str, ToolParameter] = {
        "query": ToolParameter(
            description="valid OpenSearch Piped Processing Language (PPL) query to suggest to users for execution",
            type="string",
            required=True,
            items=ToolParameter(
                type="object",
                properties={
                    "id": ToolParameter(type="string", required=True),
                    "content": ToolParameter(type="string", required=True),
                    "status": ToolParameter(type="string", required=True),
                },
            ),
        ),
    }

    def _invoke(
            self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        try:
            query = params.get("query", [])
            response_data = {
                "query": query
            }
            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=response_data,
                params=params,
            )

        except Exception as e:
            logging.exception(f"error using {self.name} tool")
            return StructuredToolResult(
                status=StructuredToolResultStatus.ERROR,
                error=f"Failed to process tasks: {str(e)}",
                params=params,
            )

    def get_parameterized_one_liner(self, params: Dict) -> str:
        query = params.get("query", [])
        return f"OpenSearchQueryToolset: Query ({query})"


class OpenSearchQueryAssistToolset(Toolset):
    """OpenSearch query assist with PPL queries"""

    def __init__(self):
        super().__init__(
            name="opensearch/query_assist",
            description="OpenSearch query assist with PPL queries.",
            experimental=True,
            enabled=True,
            tools=[PplQueryAssistTool()],
            tags=[ToolsetTag.CORE],
            is_default=True,
        )

    def get_example_config(self) -> Dict[str, Any]:
        return {}

    def _reload_instructions(self):
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "opensearch_query_assist_instructions.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")
