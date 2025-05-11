import re

# parses both simple types: "int", "array", "string"
# but also arrays of those simpler types: "array[int]", "array[string]", etc.
pattern = r"^(array\[(?P<inner_type>\w+)\])|(?P<simple_type>\w+)$"


def type_to_open_ai_schema(type_value):
    match = re.match(pattern, type_value.strip())

    if not match:
        raise ValueError(f"Invalid type format: {type_value}")

    if match.group("inner_type"):
        return {"type": "array", "items": {"type": match.group("inner_type")}}

    else:
        return {"type": match.group("simple_type")}


def format_tool_to_open_ai_standard(
    tool_name: str, tool_description: str, tool_parameters: dict
):
    tool_properties = {}
    for param_name, param_attributes in tool_parameters.items():
        tool_properties[param_name] = type_to_open_ai_schema(param_attributes.type)
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
                    if param_attributes.required
                ],
                "type": "object",
            },
        },
    }

    # gemini doesnt have parameters object if it is without params
    if tool_properties is None or tool_properties == {}:
        result["function"].pop("parameters")  # type: ignore

    return result
