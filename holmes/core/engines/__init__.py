"""Pluggable agent engines.

An engine is a ``ToolCallingLLM`` subclass that overrides ``call_stream`` with
a different agent loop (an OSS harness) while keeping the same inputs, the
same ``StreamEvents`` and the same OpenAI-format history. Callers select one
by id; everything above ``call_stream`` is unchanged.
"""

import importlib
import importlib.util
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


def resolve_engine(requested: Optional[str], config_default: Optional[str]) -> str:
    """Pick the engine for a request: per-request value, then the configured default, then legacy."""
    return validate_engine_id(requested or config_default or LEGACY_ENGINE)


class AgentPauseRequested(Exception):
    """Raised inside a harness engine's model adapter to stop the run for a pause.

    The tool wrappers record pending approvals and frontend tool calls while
    the harness runs its tool batch; when the harness asks for the next model
    call the adapter raises this instead, and the engine turns it into the
    APPROVAL_REQUIRED event the legacy loop emits after its own batch.
    """

    def __init__(self, pending_approvals: list, pending_frontend_calls: list) -> None:
        super().__init__("agent run paused for approval or frontend tools")
        self.pending_approvals = pending_approvals
        self.pending_frontend_calls = pending_frontend_calls
