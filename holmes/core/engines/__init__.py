"""Pluggable agent engines.

An engine is a ``ToolCallingLLM`` subclass that overrides ``call_stream`` with
a different agent loop (an OSS harness) while keeping the same inputs, the
same ``StreamEvents`` and the same OpenAI-format history. Callers select one
by id; everything above ``call_stream`` is unchanged.
"""

import importlib
import importlib.util
import logging
from typing import TYPE_CHECKING, Optional, Type

if TYPE_CHECKING:
    from holmes.core.tool_calling_llm import ToolCallingLLM

LEGACY_ENGINE = "legacy"
OPENAI_AGENTS_ENGINE = "openai_agents"
PYDANTIC_AI_ENGINE = "pydantic_ai"
LANGGRAPH_ENGINE = "langgraph"

ENGINE_IDS = (
    LEGACY_ENGINE,
    OPENAI_AGENTS_ENGINE,
    PYDANTIC_AI_ENGINE,
    LANGGRAPH_ENGINE,
)

# engine id -> (module with the engine class, class name, top-level package the
# Poetry group installs, Poetry group name)
_ENGINE_SPECS = {
    OPENAI_AGENTS_ENGINE: (
        "holmes.core.engines.openai_agents.engine",
        "OpenAIAgentsToolCallingLLM",
        "agents",
        "engine-openai-agents",
    ),
    PYDANTIC_AI_ENGINE: (
        "holmes.core.engines.pydantic_ai.engine",
        "PydanticAIToolCallingLLM",
        "pydantic_ai",
        "engine-pydantic-ai",
    ),
    LANGGRAPH_ENGINE: (
        "holmes.core.engines.langgraph.engine",
        "LangGraphToolCallingLLM",
        "langgraph",
        "engine-langgraph",
    ),
}


class UnknownEngineError(ValueError):
    pass


class EngineNotInstalledError(RuntimeError):
    pass


def validate_engine_id(engine_id: str) -> str:
    if engine_id not in ENGINE_IDS:
        raise UnknownEngineError(
            f"Unknown agent engine {engine_id!r}. Valid engines: {', '.join(ENGINE_IDS)}"
        )
    return engine_id


def is_engine_installed(engine_id: str) -> bool:
    validate_engine_id(engine_id)
    if engine_id == LEGACY_ENGINE:
        return True
    package = _ENGINE_SPECS[engine_id][2]
    return importlib.util.find_spec(package) is not None


def installed_engines() -> list[str]:
    return [e for e in ENGINE_IDS if is_engine_installed(e)]


def get_engine_class(engine_id: str) -> Type["ToolCallingLLM"]:
    """Return the ``ToolCallingLLM`` subclass implementing ``engine_id``.

    Imports lazily so the optional harness packages are only needed when an
    engine is actually selected.
    """
    validate_engine_id(engine_id)
    if engine_id == LEGACY_ENGINE:
        from holmes.core.tool_calling_llm import ToolCallingLLM

        return ToolCallingLLM

    module_name, class_name, package, group = _ENGINE_SPECS[engine_id]
    if importlib.util.find_spec(package) is None:
        raise EngineNotInstalledError(
            f"Agent engine {engine_id!r} needs the {package!r} package. "
            f"Install it with: poetry install --with {group}"
        )
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def resolve_engine(
    requested: Optional[str],
    config_default: Optional[str],
    *,
    needs_legacy: bool = False,
    reason: str = "",
) -> str:
    """Pick the engine for a request.

    Order: per-request value, then the configured default, then legacy.
    Features the new engines do not support yet (tool approvals, pause-mode
    frontend tools, resumes) force the legacy engine.
    """
    engine_id = validate_engine_id(requested or config_default or LEGACY_ENGINE)
    if needs_legacy and engine_id != LEGACY_ENGINE:
        logging.info(
            f"Agent engine {engine_id!r} does not support {reason or 'this request'}; "
            f"falling back to the {LEGACY_ENGINE!r} engine"
        )
        return LEGACY_ENGINE
    return engine_id


def legacy_requirement(
    *,
    enable_tool_approval: bool = False,
    tool_decisions: Optional[list] = None,
    frontend_tool_results: Optional[list] = None,
    frontend_tools: Optional[list] = None,
) -> Optional[str]:
    """Return why a request must run on the legacy engine, or None.

    The harness engines implement the plain loop only; anything that pauses
    the stream or resumes it from client state is legacy-only for now.
    """
    if enable_tool_approval:
        return "tool approvals"
    if tool_decisions:
        return "resuming from tool decisions"
    if frontend_tool_results:
        return "resuming from frontend tool results"
    for tool in frontend_tools or []:
        if getattr(tool, "mode", "pause") == "pause":
            return "pause-mode frontend tools"
    return None
