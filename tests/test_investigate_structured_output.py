from typing import Any, Optional, Tuple
import pytest
from holmes.core.investigation_structured_output import (
    DEFAULT_SECTIONS,
    get_output_format_for_investigation,
    process_response_into_sections,
)
from holmes.plugins.prompts import load_and_render_prompt


def test_prompt_sections_formatting():
    issue = {"source_type": "prometheus"}
    prompt = load_and_render_prompt(
        "builtin://generic_investigation.jinja2",
        {"issue": issue, "sections": DEFAULT_SECTIONS},
    )

    assert len(DEFAULT_SECTIONS) > 0
    for title, description in DEFAULT_SECTIONS.items():
        expected_section = f"- {title}: {description}"
        assert (
            expected_section in prompt
        ), f'Expected section "{title}" not found in formatted prompt'


def test_get_output_format_for_investigation():
    output_format = get_output_format_for_investigation(
        {"Title1": "Description1", "Title2": "Description2"}
    )

    assert output_format
    assert output_format["json_schema"]
    assert output_format["json_schema"]["schema"]
    assert output_format["json_schema"]["schema"]["properties"]

    assert output_format["json_schema"]["schema"]["properties"] == {
        "Title1": {"type": ["string", "null"], "description": "Description1"},
        "Title2": {"type": ["string", "null"], "description": "Description2"},
    }

    assert output_format["json_schema"]["schema"]["required"] == ["Title1", "Title2"]



@pytest.mark.parametrize("input_response,expected_text,expected_sections", [
    ({"section1": "test1", "section2": "test2"}, "\n# section1\ntest1\n\n# section2\ntest2\n", {"section1": "test1", "section2": "test2"}),
    ('{"section1": "test1", "section2": "test2"}', "\n# section1\ntest1\n\n# section2\ntest2\n", {"section1": "test1", "section2": "test2"}),
    ('```json\n{"section1": "test1", "section2": "test2"}\n```', "\n# section1\ntest1\n\n# section2\ntest2\n", {"section1": "test1", "section2": "test2"}),
    (123, "123", None),
    (None, "None", None),
    ("plain text", "plain text", None),
    ('{"invalid": json}', '{"invalid": json}', None),
    ([], "[]", None),
    ({}, "{}", None)
])
def test_process_response_into_sections(input_response: Any, expected_text:str, expected_sections:Optional[dict]):
    (text, sections) = process_response_into_sections(input_response)
    print(f"* ACTUAL\n{text}")
    print(f"* EXPECTED\n{expected_text}")
    assert text == expected_text
    assert sections == expected_sections

@pytest.mark.parametrize("invalid_json", [
    '{"key": value}',
    '{key: "value"}',
    'not json at all'
])
def test_process_response_invalid_json(invalid_json):
    result = process_response_into_sections(invalid_json)
    assert result == (invalid_json, None)
