from holmes.plugins.prompts import load_and_render_prompt

template = "builtin://_toolsets_instructions.jinja2"


def test_empty_when_no_toolsets():
    """Test that template returns empty string when no toolsets are provided."""
    result = load_and_render_prompt(template, {"enabled_toolsets": []})
    assert result == ""


def test_empty_when_toolsets_without_llm_instructions():
    """Test that template returns empty when toolsets have no llm_instructions."""
    toolsets = [
        {"name": "Tool1", "llm_instructions": ""},
        {"name": "Tool2", "llm_instructions": None},
    ]
    result = load_and_render_prompt(template, {"enabled_toolsets": toolsets})
    print(f"** result:\n{result}")
    assert result == ""


def test_renders_single_toolset_with_instructions():
    """Test that template properly renders toolsets with llm_instructions."""
    toolsets = [
        {"name": "Tool1", "llm_instructions": ""},
        {"name": "Tool2", "llm_instructions": ""},
        {"name": "Tool3", "llm_instructions": "\nInstructions for Tool3"},
        {"name": "Tool4", "llm_instructions": ""},
        {"name": "Tool5", "llm_instructions": ""},
    ]
    result = load_and_render_prompt(template, {"enabled_toolsets": toolsets})
    expected = "# Available Toolsets\n\n## Tool3\n\nInstructions for Tool3"
    print(f"** result:\n{result}")
    print(f"** expected:\n{expected}")
    assert result == expected


def test_renders_toolsets_with_instructions():
    """Test that template properly renders toolsets with llm_instructions."""
    toolsets = [
        {"name": "Tool1", "llm_instructions": "\nInstructions for Tool1"},
        {"name": "Tool2", "llm_instructions": ""},
        {"name": "Tool3", "llm_instructions": "\nInstructions for Tool3"},
        {"name": "Tool4", "llm_instructions": ""},
        {"name": "Tool5", "llm_instructions": "\nInstructions for Tool5"},
    ]
    result = load_and_render_prompt(template, {"enabled_toolsets": toolsets})
    expected = "# Available Toolsets\n\n## Tool1\n\nInstructions for Tool1\n\n## Tool3\n\nInstructions for Tool3\n\n## Tool5\n\nInstructions for Tool5"
    print(f"** result:\n{result}")
    print(f"** expected:\n{expected}")
    assert result == expected
