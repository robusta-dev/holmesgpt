import re
from typing import Any, Optional

from holmes.common.env_vars import (
    TOOL_SCHEMA_NO_PARAM_OBJECT_IF_NO_PARAMS,
    LLMS_WITH_STRICT_TOOL_CALLS,
)
from holmes.utils.llms import model_matches_list

# parses both simple types: "int", "array", "string"
# but also arrays of those simpler types: "array[int]", "array[string]", etc.
pattern = r"^(array\[(?P<inner_type>\w+)\])|(?P<simple_type>\w+)$"

LLMS_WITH_STRICT_TOOL_CALLS_LIST = [
    llm.strip() for llm in LLMS_WITH_STRICT_TOOL_CALLS.split(",")
]


def type_to_open_ai_schema(param_attributes: Any, strict_mode: bool):
    match = re.match(pattern, param_attributes.type.strip())

    type_obj: Optional[dict[str, Any]] = None
    if not match:
        raise ValueError(f"Invalid type format: {param_attributes.type.strip()}")

    if match.group("inner_type"):
        type_obj = {"type": "array", "items": {"type": match.group("inner_type")}}

    else:
        type_obj = {"type": match.group("simple_type")}

    if type_obj and not param_attributes.required:
        type_obj["type"] = [type_obj["type"], "null"]

    return type_obj


def format_tool_to_open_ai_standard(
    tool_name: str, tool_description: str, tool_parameters: dict, target_model: str
):
    tool_properties = {}

    strict_mode = model_matches_list(target_model, LLMS_WITH_STRICT_TOOL_CALLS_LIST)

    for param_name, param_attributes in tool_parameters.items():
        tool_properties[param_name] = type_to_open_ai_schema(
            param_attributes=param_attributes, strict_mode=strict_mode
        )
        if param_attributes.description is not None:
            tool_properties[param_name]["description"] = param_attributes.description

    result: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_description,
            "parameters": {
                "properties": tool_properties,
                "required": [
                    param_name
                    for param_name, param_attributes in tool_parameters.items()
                    if param_attributes.required or strict_mode
                ],
                "type": "object",
            },
        },
    }

    if strict_mode:
        result["function"]["strict"] = True
        result["function"]["parameters"]["additionalProperties"] = False

    # gemini doesnt have parameters object if it is without params
    if TOOL_SCHEMA_NO_PARAM_OBJECT_IF_NO_PARAMS and (
        tool_properties is None or tool_properties == {}
    ):
        result["function"].pop("parameters")  # type: ignore

    return result
