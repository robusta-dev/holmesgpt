import importlib.util
from unittest.mock import MagicMock

import pytest

from holmes.config import Config
from holmes.core.engines import (
    ENGINE_IDS,
    LEGACY_ENGINE,
    EngineNotInstalledError,
    UnknownEngineError,
    get_engine_class,
    legacy_requirement,
    resolve_engine,
)
from holmes.core.models import ChatRequest, FrontendToolDefinition
from holmes.core.tool_calling_llm import ToolCallingLLM


def test_legacy_engine_is_tool_calling_llm():
    assert get_engine_class(LEGACY_ENGINE) is ToolCallingLLM
    assert ToolCallingLLM.engine_id == LEGACY_ENGINE


def test_unknown_engine_rejected():
    with pytest.raises(UnknownEngineError):
        get_engine_class("bogus")
    with pytest.raises(UnknownEngineError):
        resolve_engine("bogus", None)


def test_resolve_order_request_then_config_then_legacy():
    assert resolve_engine(None, None) == LEGACY_ENGINE
    assert resolve_engine(None, "pydantic_ai") == "pydantic_ai"
    assert resolve_engine("langgraph", "pydantic_ai") == "langgraph"


def test_resolve_falls_back_to_legacy_when_required():
    assert resolve_engine("langgraph", None, needs_legacy=True, reason="x") == LEGACY_ENGINE
    assert resolve_engine(LEGACY_ENGINE, None, needs_legacy=True) == LEGACY_ENGINE


def test_missing_package_gives_install_hint(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    with pytest.raises(EngineNotInstalledError) as exc:
        get_engine_class("openai_agents")
    assert "poetry install --with engine-openai-agents" in str(exc.value)


def test_legacy_requirement():
    assert legacy_requirement() is None
    assert legacy_requirement(enable_tool_approval=True) == "tool approvals"
    assert legacy_requirement(tool_decisions=[object()]) == "resuming from tool decisions"
    assert legacy_requirement(frontend_tool_results=[object()]) == "resuming from frontend tool results"
    pause = FrontendToolDefinition(name="t", description="d", mode="pause")
    noop = FrontendToolDefinition(name="t", description="d", mode="noop")
    assert legacy_requirement(frontend_tools=[noop]) is None
    assert legacy_requirement(frontend_tools=[noop, pause]) == "pause-mode frontend tools"


def test_with_executor_keeps_engine_subclass():
    class FakeEngine(ToolCallingLLM):
        engine_id = "fake"

    ai = FakeEngine(tool_executor=MagicMock(), max_steps=3, llm=MagicMock(), tool_results_dir=None)
    clone = ai.with_executor(MagicMock())
    assert type(clone) is FakeEngine
    assert clone.max_steps == 3 and clone.llm is ai.llm


def test_chat_request_accepts_engine():
    req = ChatRequest(ask="hi", engine="pydantic_ai")
    assert req.engine == "pydantic_ai"
    assert ChatRequest(ask="hi").engine is None


def test_config_reads_agent_engine_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_ENGINE", "langgraph")
    config = Config()
    config._apply_env_fallbacks()
    assert config.agent_engine == "langgraph"

    monkeypatch.setenv("AGENT_ENGINE", "nope")
    config = Config()
    with pytest.raises(UnknownEngineError):
        config._apply_env_fallbacks()


def test_config_explicit_engine_wins_over_env(monkeypatch):
    monkeypatch.setenv("AGENT_ENGINE", "langgraph")
    config = Config(agent_engine="pydantic_ai")
    config._apply_env_fallbacks()
    assert config.agent_engine == "pydantic_ai"


def test_all_engine_ids_known():
    assert set(ENGINE_IDS) == {"legacy", "openai_agents", "pydantic_ai", "langgraph"}
