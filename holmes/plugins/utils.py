# this file contains utilities that plugin writers are likely to use - not utilities that are only relevant for core
from typing import Dict


def dict_to_markdown(items: Dict[str, str]) -> str:
    if not items:
        return ""

    text = ""
    for k, v in items.items():
        # TODO: if v is a url, linkify it
        text += f"• *{k}*: {v}\n"

    return text
