from typing import Dict
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.tools import (
    StaticPrerequisite,
    StructuredToolResult,
    Tool,
    ToolResultStatus,
    Toolset,
)

template = "builtin://_toolsets_instructions.jinja2"


class DummyTool(Tool):
    def __init__(self):
        super().__init__(name="dummy_tool_name", description="tool description")

    def _invoke(self, params):
        return StructuredToolResult(status=ToolResultStatus.SUCCESS, data="")

    def get_parameterized_one_liner(self, params: Dict) -> str:
        return ""


class MockToolset(Toolset):
    def __init__(self, config: dict):
        if not config.get("description"):
            config["description"] = config.get("name")
        if config.get("enabled") is None:
            config["enabled"] = True
        config["tools"] = [DummyTool()]

        super().__init__(**config)
        if self.enabled:
            self.check_prerequisites()

    def get_example_config(self):
        return {}


def test_empty_when_no_toolsets():
    """Test that template returns empty string when no toolsets are provided."""
    result = load_and_render_prompt(template, {"toolsets": []})
    assert result == ""


def test_empty_when_toolsets_without_llm_instructions():
    """Test that template returns empty when toolsets have no llm_instructions."""
    toolsets = [
        MockToolset({"name": "Tool1", "llm_instructions": ""}),
        MockToolset({"name": "Tool2", "llm_instructions": None}),
    ]
    result = load_and_render_prompt(template, {"toolsets": toolsets})
    print(f"** result:\n{result}")
    assert result == ""


def test_renders_single_toolset_with_instructions():
    """Test that template properly renders toolsets with llm_instructions."""
    toolsets = [
        MockToolset({"name": "Tool1", "llm_instructions": ""}),
        MockToolset({"name": "Tool2", "llm_instructions": ""}),
        MockToolset({"name": "Tool3", "llm_instructions": "\nInstructions for Tool3"}),
        MockToolset({"name": "Tool4", "llm_instructions": ""}),
        MockToolset({"name": "Tool5", "llm_instructions": ""}),
    ]
    result = load_and_render_prompt(template, {"toolsets": toolsets})
    expected = "# Available Toolsets\n\n## Tool3\n\nInstructions for Tool3"
    print(f"** result:\n{result}")
    print(f"** expected:\n{expected}")
    assert result == expected


def test_renders_toolsets_with_instructions():
    """Test that template properly renders toolsets with llm_instructions."""
    toolsets = [
        MockToolset({"name": "Tool1", "llm_instructions": "\nInstructions for Tool1"}),
        MockToolset({"name": "Tool2", "llm_instructions": ""}),
        MockToolset({"name": "Tool3", "llm_instructions": "\nInstructions for Tool3"}),
        MockToolset({"name": "Tool4", "llm_instructions": ""}),
        MockToolset({"name": "Tool5", "llm_instructions": "\nInstructions for Tool5"}),
    ]
    result = load_and_render_prompt(template, {"toolsets": toolsets})
    expected = "# Available Toolsets\n\n## Tool1\n\nInstructions for Tool1\n\n## Tool3\n\nInstructions for Tool3\n\n## Tool5\n\nInstructions for Tool5"
    print(f"** result:\n{result}")
    print(f"** expected:\n{expected}")
    assert result == expected


def test_renders_disabled_toolsets():
    toolsets = [
        MockToolset(
            {"name": "Toolset1", "description": "this is tool 1", "enabled": False}
        ),
        MockToolset(
            {
                "name": "Toolset2",
                "description": "this is tool 2",
                "enabled": True,
                "docs_url": "https://example.com",
                "prerequisites": [
                    StaticPrerequisite(
                        enabled=False, disabled_reason="Health check failed"
                    )
                ],
            }
        ),
    ]
    result = load_and_render_prompt(template, {"toolsets": toolsets})
    expected = """
* toolset name: Toolset1
    *  status: disabled
    *  description: this is tool 1
* toolset name: Toolset2
    *  status: The toolset is enabled but misconfigured and failed to initialize.
    *  error: Health check failed
    *  description: this is tool 2
    *  setup instructions: https://example.com
""".strip()
    print(f"** result:\n{result}")
    print(f"** expected:\n{expected}")
    assert expected in result
