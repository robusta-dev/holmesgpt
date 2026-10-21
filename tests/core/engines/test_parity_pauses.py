"""Approvals, frontend pauses, resumes, OAuth and compaction must match the legacy loop."""

import copy
import json

import pytest

from holmes.core.models import FrontendToolDefinition, FrontendToolResult, ToolApprovalDecision
from holmes.core.tools_utils.frontend_tools import inject_frontend_tools
from holmes.utils.approval_tokens import ApprovalTokenError, verify_token
from holmes.utils.stream import StreamEvents

from tests.core.engines.fakes import (
    BASE_MESSAGES,
    BigAnswerTool,
    OAuthTool,
    ScriptedLLM,
    SmallWindowLLM,
    llm_response,
    make_engine_with,
    make_toolset_with,
)
from tests.core.engines.test_parity import (
    ALL_ENGINES,
    HARNESS_ENGINES,
    LEGACY_ENGINE,
    normalized_event_names,
    normalized_messages,
)


def run(engine, msgs, **kwargs):
    return list(engine.call_stream(msgs=copy.deepcopy(msgs), **kwargs))


def last(events):
    return events[-1]


def strip_tokens(messages):
    """Approval tokens are time-based; compare everything else."""
    out = []
    for m in copy.deepcopy(messages):
        for tc in m.get("tool_calls") or []:
            if "approval_token" in tc:
                tc["approval_token"] = "<token>"
        out.append(m)
    return out


def assert_same(events, legacy_events):
    assert normalized_event_names(events) == normalized_event_names(legacy_events)
    end, legacy_end = last(events).data, last(legacy_events).data
    assert normalized_messages(strip_tokens(end["messages"])) == normalized_messages(
        strip_tokens(legacy_end["messages"])
    )
    assert end["num_llm_calls"] == legacy_end["num_llm_calls"]
    assert end["costs"] == legacy_end["costs"]
    for key in ("pending_approvals", "pending_frontend_tool_calls", "content"):
        assert end.get(key) == legacy_end.get(key)


def approval_scenario():
    return [
        llm_response(
            "Checking.",
            [("tc_gated", "echo", json.dumps({"text": "gated"})), ("tc_free", "async_inside", "{}")],
        ),
        llm_response("Done after approval."),
    ]


def make_approval_engine(engine_id, responses):
    return make_engine_with(engine_id, ScriptedLLM(responses), make_toolset_with(approval_required_tools=["echo"]))


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_approval_pauses_the_run(engine_id):
    legacy = run(make_approval_engine(LEGACY_ENGINE, approval_scenario()), BASE_MESSAGES, enable_tool_approval=True)
    events = run(make_approval_engine(engine_id, approval_scenario()), BASE_MESSAGES, enable_tool_approval=True)
    assert_same(events, legacy)

    pause = last(events)
    assert pause.event == StreamEvents.APPROVAL_REQUIRED
    assert [a["tool_call_id"] for a in pause.data["pending_approvals"]] == ["tc_gated"]
    assistant = [m for m in pause.data["messages"] if m["role"] == "assistant"][-1]
    gated = [tc for tc in assistant["tool_calls"] if tc["id"] == "tc_gated"][0]
    assert gated["pending_approval"] is True
    # verify_token raises ApprovalTokenError on a bad or mismatched token.
    verify_token(gated["approval_token"], "tc_gated", "echo", gated["function"]["arguments"])
    with pytest.raises(ApprovalTokenError):
        verify_token(gated["approval_token"], "tc_gated", "echo", '{"text": "tampered"}')
    tool_messages = [m for m in pause.data["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["tc_free"]


@pytest.mark.parametrize("engine_id", ALL_ENGINES)
@pytest.mark.parametrize("approved", [True, False])
def test_resume_from_tool_decisions(engine_id, approved):
    def resumed(eid):
        engine = make_approval_engine(eid, approval_scenario())
        pause = last(run(engine, BASE_MESSAGES, enable_tool_approval=True))
        decision = ToolApprovalDecision(tool_call_id="tc_gated", approved=approved, feedback=None if approved else "no thanks")
        return run(
            engine,
            pause.data["messages"],
            enable_tool_approval=True,
            tool_decisions=[decision],
            iteration_offset=pause.data["num_llm_calls"],
        )

    legacy_events = resumed(LEGACY_ENGINE)
    events = resumed(engine_id)
    assert_same(events, legacy_events)
    end = last(events)
    assert end.event == StreamEvents.ANSWER_END
    assert end.data["content"] == "Done after approval."
    gated_msg = [m for m in end.data["messages"] if m.get("tool_call_id") == "tc_gated"][0]
    if approved:
        assert "echo:" in gated_msg["content"]
    else:
        assert "no thanks" in gated_msg["content"] or "rejected" in gated_msg["content"].lower()


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_approval_disabled_rejects_in_place(engine_id):
    legacy = run(make_approval_engine(LEGACY_ENGINE, approval_scenario()), BASE_MESSAGES)
    events = run(make_approval_engine(engine_id, approval_scenario()), BASE_MESSAGES)
    assert_same(events, legacy)
    assert last(events).event == StreamEvents.ANSWER_END
    gated = [t for t in last(events).data["tool_calls"] if t["tool_call_id"] == "tc_gated"][0]
    assert gated["result"]["status"] == "error"
    assert "NOT executed" in gated["result"]["error"]


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_oauth_pauses_even_without_approvals(engine_id):
    def make(eid):
        return make_engine_with(
            eid,
            ScriptedLLM([llm_response(None, [("tc_oauth", "connect_service", "{}")]), llm_response("never")]),
            make_toolset_with(OAuthTool()),
        )

    legacy = run(make(LEGACY_ENGINE), BASE_MESSAGES)
    events = run(make(engine_id), BASE_MESSAGES)
    assert_same(events, legacy)
    assert last(events).event == StreamEvents.APPROVAL_REQUIRED
    assert "__oauth_metadata" in last(events).data["pending_approvals"][0]["params"]


def frontend_defs():
    return [
        FrontendToolDefinition(
            name="ask_user",
            description="Ask the user something",
            parameters={"type": "object", "properties": {"question": {"type": "string"}}},
            mode="pause",
        ),
        FrontendToolDefinition(name="notify", description="Fire and forget", parameters={}, mode="noop"),
    ]


def frontend_scenario():
    return [
        llm_response(
            None,
            [
                ("tc_ask", "ask_user", json.dumps({"question": "which namespace?"})),
                ("tc_notify", "notify", "{}"),
                ("tc_echo", "echo", "{}"),
            ],
        ),
        llm_response("Thanks, using prod."),
    ]


def make_frontend_engine(eid, responses):
    engine = make_engine_with(eid, ScriptedLLM(responses), make_toolset_with())
    request_ai, has_pause = inject_frontend_tools(engine, frontend_defs())
    assert has_pause
    assert type(request_ai) is type(engine)
    return request_ai


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_frontend_pause_tool(engine_id):
    legacy = run(make_frontend_engine(LEGACY_ENGINE, frontend_scenario()), BASE_MESSAGES)
    events = run(make_frontend_engine(engine_id, frontend_scenario()), BASE_MESSAGES)
    assert_same(events, legacy)
    pause = last(events)
    assert pause.event == StreamEvents.APPROVAL_REQUIRED
    assert [c["tool_call_id"] for c in pause.data["pending_frontend_tool_calls"]] == ["tc_ask"]
    assistant = [m for m in pause.data["messages"] if m["role"] == "assistant"][-1]
    assert [tc for tc in assistant["tool_calls"] if tc["id"] == "tc_ask"][0]["pending_frontend"] is True
    tool_ids = sorted(m["tool_call_id"] for m in pause.data["messages"] if m["role"] == "tool")
    assert tool_ids == ["tc_echo", "tc_notify"]  # noop tool answered immediately, pause tool not


@pytest.mark.parametrize("engine_id", ALL_ENGINES)
def test_resume_from_frontend_results(engine_id):
    def resumed(eid):
        engine = make_frontend_engine(eid, frontend_scenario())
        pause = last(run(engine, BASE_MESSAGES))
        return run(
            engine,
            pause.data["messages"],
            frontend_tool_results=[FrontendToolResult(tool_call_id="tc_ask", tool_name="ask_user", result="prod")],
            iteration_offset=pause.data["num_llm_calls"],
        )

    legacy_events = resumed(LEGACY_ENGINE)
    events = resumed(engine_id)
    assert_same(events, legacy_events)
    end = last(events)
    assert end.event == StreamEvents.ANSWER_END
    assert end.data["content"] == "Thanks, using prod."
    assert any(m.get("tool_call_id") == "tc_ask" and "prod" in str(m["content"]) for m in end.data["messages"])


@pytest.mark.parametrize("engine_id", ALL_ENGINES)
def test_abandoned_approval_is_denied_on_new_question(engine_id):
    def resumed(eid):
        engine = make_approval_engine(eid, approval_scenario())
        pause = last(run(engine, BASE_MESSAGES, enable_tool_approval=True))
        history = pause.data["messages"] + [{"role": "user", "content": "never mind, something else"}]
        return run(engine, history, enable_tool_approval=True)

    legacy_events = resumed(LEGACY_ENGINE)
    events = resumed(engine_id)
    assert_same(events, legacy_events)
    end = last(events).data
    denied = [m for m in end["messages"] if m.get("tool_call_id") == "tc_gated"]
    assert denied and "cancelled" in str(denied[0]["content"]).lower()
    assert end["content"] == "Done after approval."


# Window and history sized so the history crosses the 95% compaction threshold
# but still fits one summarization request (window - max output - instructions).
COMPACTION_WINDOW = 20000
COMPACTION_MAX_OUTPUT = 500


def compaction_history():
    return [
        {"role": "system", "content": "You are Holmes."},
        {"role": "user", "content": "Tell me everything about the cluster."},
        {"role": "assistant", "content": "Here is a very long report. " + ("blah " * 14800)},
        {"role": "user", "content": "And now, how many pods are there?"},
    ]


def compaction_scenario():
    return [
        llm_response("Conversation summary: the cluster was described at length.", cost=0.0005),
        llm_response(None, [("tc1", "echo", json.dumps({"text": "pods"}))]),
        llm_response("There are 3 pods.", cost=0.002),
    ]


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_compaction_before_model_call(engine_id):
    def make(eid):
        llm = SmallWindowLLM(compaction_scenario(), context_window=COMPACTION_WINDOW, max_output=COMPACTION_MAX_OUTPUT)
        return make_engine_with(eid, llm, make_toolset_with(BigAnswerTool()))

    legacy_events = run(make(LEGACY_ENGINE), compaction_history())
    events = run(make(engine_id), compaction_history())
    assert_same(events, legacy_events)
    names = [e.event for e in events]
    assert StreamEvents.CONVERSATION_HISTORY_COMPACTION_START in names
    assert StreamEvents.CONVERSATION_HISTORY_COMPACTED in names
    end = last(events).data
    assert end["costs"]["num_compactions"] == 1
    assert end["content"] == "There are 3 pods."
    assert len(end["messages"]) < len(compaction_history()) + 3
    assert any("summary" in str(m.get("content", "")).lower() for m in end["messages"])
