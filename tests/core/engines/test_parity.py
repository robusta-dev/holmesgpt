"""Every engine must produce the same events, history and accounting as the legacy loop."""

import copy
import json
import threading
import time

import pytest

from holmes.core.engines import ENGINE_IDS, LEGACY_ENGINE, is_engine_installed
from holmes.core.tool_calling_llm import LLMInterruptedError
from holmes.utils.stream import StreamEvents

from tests.core.engines.fakes import BASE_MESSAGES, llm_response, make_engine

HARNESS_ENGINES = [
    pytest.param(e, marks=pytest.mark.skipif(not is_engine_installed(e), reason=f"{e} not installed"))
    for e in ENGINE_IDS
    if e != LEGACY_ENGINE
]
ALL_ENGINES = [LEGACY_ENGINE] + HARNESS_ENGINES


def run_engine(engine_id, responses, max_steps=10, cancel_event=None):
    engine, llm = make_engine(engine_id, responses, max_steps=max_steps)
    events = list(
        engine.call_stream(msgs=copy.deepcopy(BASE_MESSAGES), cancel_event=cancel_event)
    )
    return events, llm


def normalized_event_names(events):
    """Tool events inside one batch may complete in any order; sort each batch."""
    out, batch = [], []
    for ev in events:
        if ev.event in (StreamEvents.START_TOOL, StreamEvents.TOOL_RESULT):
            key = ev.data.get("id") or ev.data.get("tool_call_id")
            batch.append((ev.event.value, key))
        else:
            if batch:
                out.append(tuple(sorted(batch)))
                batch = []
            out.append(ev.event.value)
    if batch:
        out.append(tuple(sorted(batch)))
    return out


def normalized_messages(messages):
    """Tool messages after one assistant turn may be appended in any order."""
    out, batch = [], []
    for m in messages:
        if m.get("role") == "tool":
            batch.append(m)
        else:
            if batch:
                out.extend(sorted(batch, key=lambda t: t["tool_call_id"]))
                batch = []
            out.append(m)
    if batch:
        out.extend(sorted(batch, key=lambda t: t["tool_call_id"]))
    return out


def answer_end(events):
    assert events[-1].event == StreamEvents.ANSWER_END
    return events[-1].data


def assert_parity(engine_id, responses_factory, max_steps=10):
    legacy_events, legacy_llm = run_engine(LEGACY_ENGINE, responses_factory(), max_steps)
    events, llm = run_engine(engine_id, responses_factory(), max_steps)

    assert normalized_event_names(events) == normalized_event_names(legacy_events)
    legacy_end, end = answer_end(legacy_events), answer_end(events)
    assert end["content"] == legacy_end["content"]
    assert normalized_messages(end["messages"]) == normalized_messages(legacy_end["messages"])
    assert end["num_llm_calls"] == legacy_end["num_llm_calls"]
    assert end["costs"] == legacy_end["costs"]
    assert end["metadata"].get("finish_reason") == legacy_end["metadata"].get("finish_reason")
    assert end["metadata"]["engine"] == engine_id

    def tool_summary(tool_calls):
        return sorted(
            (t["tool_call_id"], t["tool_name"], t["result"]["status"], t["result"].get("data"))
            for t in tool_calls
        )

    assert tool_summary(end["tool_calls"]) == tool_summary(legacy_end["tool_calls"])
    # Every LLM request must be byte-identical: same messages, tools and tool_choice.
    assert len(llm.calls) == len(legacy_llm.calls)
    for mine, theirs in zip(llm.calls, legacy_llm.calls):
        assert normalized_messages(mine["messages"]) == normalized_messages(theirs["messages"])
        assert mine["tools"] == theirs["tools"]
        assert mine["tool_choice"] == theirs["tool_choice"]
    return events, legacy_events


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_text_only_answer(engine_id):
    assert_parity(engine_id, lambda: [llm_response("All good.", cost=0.002)])


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_parallel_tools_then_answer(engine_id):
    def responses():
        return [
            llm_response(
                "Let me check.",
                [("tc_echo", "echo", json.dumps({"text": "a"})), ("tc_async", "async_inside", "{}")],
                reasoning_content="thinking...",
                cached_tokens=10,
                reasoning_tokens=5,
            ),
            llm_response("Found it.", cost=0.003, prompt_tokens=200, completion_tokens=30),
        ]

    events, _ = assert_parity(engine_id, responses)
    names = [e.event for e in events]
    assert names.count(StreamEvents.START_TOOL) == 2
    assert names.count(StreamEvents.TOOL_RESULT) == 2
    assert StreamEvents.AI_MESSAGE in names
    end = answer_end(events)
    assert end["costs"]["total_cost"] == pytest.approx(0.004)
    assert end["costs"]["cached_tokens"] == 10
    assert end["costs"]["reasoning_tokens"] == 5
    tool_msgs = [m for m in end["messages"] if m["role"] == "tool"]
    assert any("async ok" in m["content"] for m in tool_msgs)


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_max_steps_forces_final_answer(engine_id):
    def responses():
        return [
            llm_response(None, [("tc1", "echo", "{}")]),
            llm_response("Forced answer."),
        ]

    _, legacy_events = assert_parity(engine_id, responses, max_steps=2)
    _, llm = run_engine(engine_id, responses(), max_steps=2)
    # On the last allowed step tools are withheld so the model must answer.
    assert llm.calls[0]["tools"] is not None
    assert llm.calls[1]["tools"] is None
    assert llm.calls[1]["tool_choice"] is None


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_too_many_steps_raises(engine_id):
    def responses():
        return [llm_response(None, [("tc1", "echo", "{}")]), llm_response(None, [("tc2", "echo", "{}")])]

    with pytest.raises(Exception, match="Too many LLM calls"):
        run_engine(engine_id, responses(), max_steps=2)


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_tool_exception_is_fed_back(engine_id):
    def responses():
        return [llm_response(None, [("tc1", "boom", "{}")]), llm_response("It failed.")]

    events, _ = assert_parity(engine_id, responses)
    end = answer_end(events)
    assert end["tool_calls"][0]["result"]["status"] == "error"
    assert "boom" in end["tool_calls"][0]["result"]["error"]


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_malformed_arguments_run_with_empty_params(engine_id):
    def responses():
        return [llm_response(None, [("tc1", "echo", "{not json")]), llm_response("Done.")]

    events, _ = assert_parity(engine_id, responses)
    end = answer_end(events)
    assert end["tool_calls"][0]["result"]["data"] == "echo:{}"


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_unknown_tool_name(engine_id):
    def responses():
        return [llm_response(None, [("tc1", "no_such_tool", "{}")]), llm_response("Hmm.")]

    events, _ = assert_parity(engine_id, responses)
    end = answer_end(events)
    assert end["tool_calls"][0]["result"]["status"] == "error"


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_image_tool_result(engine_id):
    def responses():
        return [llm_response(None, [("tc1", "image", "{}")]), llm_response("Here is the chart.")]

    events, legacy_events = assert_parity(engine_id, responses)
    end = answer_end(events)
    tool_msg = [m for m in end["messages"] if m["role"] == "tool"][0]
    assert isinstance(tool_msg["content"], list)
    assert tool_msg["content"][1]["type"] == "image_url"


@pytest.mark.parametrize("engine_id", ALL_ENGINES)
def test_cancellation_mid_tool(engine_id):
    cancel = threading.Event()
    responses = [llm_response(None, [("tc1", "slow", json.dumps({"seconds": 1.0}))]), llm_response("never")]
    engine, _ = make_engine(engine_id, responses)
    threading.Timer(0.1, cancel.set).start()
    started = time.time()
    with pytest.raises(LLMInterruptedError):
        list(engine.call_stream(msgs=copy.deepcopy(BASE_MESSAGES), cancel_event=cancel))
    assert time.time() - started < 5


@pytest.mark.parametrize("engine_id", HARNESS_ENGINES)
def test_call_wrapper_returns_llm_result(engine_id):
    engine, _ = make_engine(engine_id, [llm_response(None, [("tc1", "echo", "{}")]), llm_response("ok")])
    result = engine.call(messages=copy.deepcopy(BASE_MESSAGES))
    assert result.result == "ok"
    assert result.num_llm_calls == 2
    assert len(result.tool_calls) == 1
    assert result.total_cost == pytest.approx(0.002)
