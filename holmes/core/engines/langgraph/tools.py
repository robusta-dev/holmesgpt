"""Schema-only ``BaseTool``s; execution happens in the middleware's ``wrap_tool_call``."""

from typing import Any, Dict, List

from langchain_core.tools import BaseTool
from pydantic import ConfigDict, Field


class HolmesLangChainTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    args_schema: Dict[str, Any]  # raw JSON schema; LangChain passes dict schemas through unvalidated
    openai_tool: Dict[str, Any] = Field(exclude=True)

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            "HolmesLangChainTool must be executed through HolmesLoopMiddleware.wrap_tool_call"
        )


def build_langchain_tools(tools_openai: list) -> List[HolmesLangChainTool]:
    out: List[HolmesLangChainTool] = []
    for d in tools_openai:
        fn = d["function"]
        out.append(
            HolmesLangChainTool(
                name=fn["name"],
                description=fn.get("description") or "",
                args_schema=fn.get("parameters") or {"type": "object", "properties": {}},
                openai_tool=d,
            )
        )
    return out
