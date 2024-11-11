

from typing import Optional
from typing_extensions import Dict, List
import re
import json
from copy import deepcopy

def stringify_tag(tag:Dict[str, str]) -> Optional[str]:
    """
    This serializes a dictionary into something more readable to the LLM.
    Although I have not seen much difference in quality of output, in theory this can help the LLM
    understand better how to link the tag values with the tools.

    Here are some examples of formatting (more can be found in the test for this function):
        - { "type": "node", "name": "my-node" }
            -> "node my-node"
        - { "type": "issue", "id": "issue-id", "name": "KubeJobFailed", "subject_namespace": "my-namespace", "subject_name": "my-pod" }
            -> issue issue-id (name=KubeJobFailed, subject_namespace=my-namespace, subject_name=my-pod)
    """
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

def format_tags_in_string(user_prompt):
    """
    Formats the tags included in a user's message.
    E.g.
        'how many pods are running on << { "type": "node", "name": "my-node" } >>?'
            -> 'how many pods are running on node my-node?'
    """
    try:
        pattern = r'<<(.*?)>>'
        match = re.search(pattern, user_prompt)

        if not match:
            return user_prompt

        json_str = match.group(1)
        json_obj = json.loads(json_str)

        formatted = stringify_tag(json_obj)
        if not formatted:
            return user_prompt

        return re.sub(pattern, formatted, user_prompt)
    except (json.JSONDecodeError, AttributeError):
        return user_prompt


def parse_messages_tags(messages:List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
        Parses the user messages for tags and format these.
        System messages and llm responses are ignored and left as-is

        This method returns a shallow copy of the messages list with the exception
        of the messages that have been parsed.
    """
    formatted_messages = []

    for message in messages:
        if message.get("role") == "user":
            formatted_str = format_tags_in_string(message.get("content"))
            if formatted_str != message.get("content"):
                formatted_message = deepcopy(message)
                formatted_message["content"] = formatted_str
                formatted_messages.append(formatted_message)
            else:
                formatted_messages.append(message)

        else:
            formatted_messages.append(message)

    return formatted_messages
