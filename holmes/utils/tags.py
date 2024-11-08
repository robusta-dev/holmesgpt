

from typing_extensions import Dict, List
import re
import json
from copy import deepcopy

def format_tag(tag:Dict[str, str]):
    type = tag.pop("type")
    if not type:
        return None

    key = ""
    if tag.get("id"):
        key = tag.pop("id")
    elif tag.get("name"):
        key = tag.pop("name")

    if not key:
        return None

    formatted_string = f"{type} {key}"

    if len(tag) > 0:
        keyVals = []
        for k, v in tag.items():
            keyVals.append(f"{k}={v}")
        formatted_string += f" ({', '.join(keyVals)})"

    return formatted_string

def format_message_tags(user_prompt):
    try:
        pattern = r'<<(.*?)>>'
        match = re.search(pattern, user_prompt)

        if not match:
            return user_prompt

        json_str = match.group(1)
        json_obj = json.loads(json_str)

        formatted = format_tag(json_obj)
        if not formatted:
            return user_prompt

        return re.sub(pattern, formatted, user_prompt)
    except (json.JSONDecodeError, AttributeError):
        return user_prompt


def format_messages_tags(messages:List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
        Parses the user messages for tags and format these.
        This method returns a shallow copy of the messages list with the exception of the messages that have been parsed.
    """
    formatted_messages = []

    for message in messages:
        if message.get("role") == "user":
            formatted_str = format_message_tags(message.get("content"))
            if formatted_str != message.get("content"):
                formatted_message = deepcopy(message)
                formatted_message["content"] = formatted_str
                formatted_messages.append(formatted_message)
            else:
                formatted_messages.append(message)

        else:
            formatted_messages.append(message)

    return formatted_messages
