from holmes.core.models import build_follow_up_actions
from holmes.utils.stream import StreamEvents, StreamMessage, add_follow_up_actions


def test_first_answer_offers_logs_graphs_articles():
    for history in (None, [], [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]):
        assert [a.id for a in build_follow_up_actions(history)] == ["logs", "graphs", "articles"]


def test_answered_conversation_offers_none():
    history = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    assert build_follow_up_actions(history) == []


def test_follow_up_actions_ride_the_terminal_events_only():
    answer_data = {"content": "done", "messages": []}
    stream = iter(
        [
            StreamMessage(event=StreamEvents.AI_MESSAGE, data={"content": "x"}),
            StreamMessage(event=StreamEvents.START_TOOL, data={"id": "t1", "tool_name": "kubectl"}),
            StreamMessage(event=StreamEvents.ANSWER_END, data=answer_data),
            StreamMessage(event=StreamEvents.APPROVAL_REQUIRED, data={"content": "approve?"}),
        ]
    )
    followups = [{"id": "logs"}]

    out = list(add_follow_up_actions(stream, followups))

    assert [m.event for m in out] == [
        StreamEvents.AI_MESSAGE,
        StreamEvents.START_TOOL,
        StreamEvents.ANSWER_END,
        StreamEvents.APPROVAL_REQUIRED,
    ]
    assert "follow_up_actions" not in out[0].data
    assert "follow_up_actions" not in out[1].data
    assert out[2].data == {"content": "done", "messages": [], "follow_up_actions": followups}
    assert out[3].data["follow_up_actions"] == followups
    # The recorder upstream keeps the message it saw.
    assert "follow_up_actions" not in answer_data
