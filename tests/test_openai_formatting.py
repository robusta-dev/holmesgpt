

import pytest
from holmes.core.openai_formatting import type_to_open_ai_schema


@pytest.mark.parametrize(
    "toolset_type, open_ai_type",
    [
        (
            "int",
            {"type": "int"},
        ),
        (
            "string",
            {"type": "string"},
        ),
        (
            "array[int]",
            {"type": "array", "items": {"type": "int"}},
        ),
        (
            "array[string]",
            {"type": "array", "items": {"type": "string"}},
        ),
    ],
)
def test_type_to_open_ai_schema(toolset_type, open_ai_type):
    result = type_to_open_ai_schema(toolset_type)
    assert result == open_ai_type
