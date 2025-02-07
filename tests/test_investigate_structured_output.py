from holmes.core.investigation_structured_output import (
    DEFAULT_SECTIONS,
    get_output_format_for_investigation,
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
