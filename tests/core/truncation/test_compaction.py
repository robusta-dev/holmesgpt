import json
import os
from pathlib import Path


from holmes.core.llm import DefaultLLM
from holmes.core.truncation.compaction import compact_conversation_history

CONVERSATION_HISTORY_FILE_PATH = (
    Path(__file__).parent / "conversation_history_for_compaction.json"
)


def test_conversation_history_compaction():
    llm = DefaultLLM(model=os.environ.get("model", "gpt-4o"))
    with open(CONVERSATION_HISTORY_FILE_PATH) as file:
        conversation_history = json.load(file)

        compacted_history = compact_conversation_history(
            original_conversation_history=conversation_history, llm=llm
        )
        assert compacted_history
        assert (
            len(compacted_history) == 3
        )  # [0]=system prompt, [1]=compacted content, [2]=message to continue

        original_tokens = llm.count_tokens_for_message(conversation_history)
        compacted_tokens = llm.count_tokens_for_message(compacted_history)
        expected_max_compacted_token_count = original_tokens * 0.2
        print(f"original_tokens={original_tokens} compacted_tokens={compacted_tokens}")
        assert (
            llm.count_tokens_for_message(compacted_history)
            < expected_max_compacted_token_count
        )
