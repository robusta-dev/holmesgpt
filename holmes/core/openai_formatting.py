import re
from typing import Any

# parses both simple types: "int", "array", "string"
# but also arrays of those simpler types: "array[int]", "array[string]", etc.
pattern = r"^(array\[(?P<inner_type>\w+)\])|(?P<simple_type>\w+)$"


def type_to_open_ai_schema(param_attributes:Any):
    match = re.match(pattern, param_attributes.type.strip())

    type_obj = None
    if not match:
        raise ValueError(f"Invalid type format: {param_attributes.type.strip()}")

    if match.group("inner_type"):
        type_obj = {"type": "array", "items": {"type": match.group("inner_type")}}

    else:
        type_obj = {"type": match.group("simple_type")}\
        
        
    if not param_attributes.required:
        type_obj["type"] = [type_obj["type"], "null"]

    return type_obj


def format_tool_to_open_ai_standard(
    tool_name: str, tool_description: str, tool_parameters: dict
):
    tool_properties = {}
    for param_name, param_attributes in tool_parameters.items():
        tool_properties[param_name] = type_to_open_ai_schema(param_attributes)
        if param_attributes.description is not None:
            tool_properties[param_name]["description"] = param_attributes.description

    result = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_description,
            "parameters": {
                "properties": tool_properties,
                "required": [
                    param_name
                    for param_name, param_attributes in tool_parameters.items()
                ],
                "type": "object",
                "additionalProperties": False
            },
            "strict": True,
        },
    }

    # gemini doesnt have parameters object if it is without params
    # if tool_properties is None or tool_properties == {}:
    #     result["function"].pop("parameters")  # type: ignore

    return result
