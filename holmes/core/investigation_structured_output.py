from typing import Any, Dict

DEFAULT_SECTIONS = {
    "Alert Explanation": '1-2 sentences explaining the alert itself - note don\'t say "The alert indicates a warning event related to a Kubernetes pod doing blah" rather just say "The pod XYZ did blah" because that is what the user actually cares about',
    "Investigation": "What you checked and found",
    "Conclusions and Possible Root causes": "What conclusions can you reach based on the data you found? what are possible root causes (if you have enough conviction to say) or what uncertainty remains. Don't say root cause but 'possible root causes'. Be clear to distinguish between what you know for certain and what is a possible explanation",
    "Next Steps": "What you would do next to troubleshoot this issue, any commands that could be run to fix it, or other ways to solve it (prefer giving precise bash commands when possible)",
    "Related logs": "Truncate and share the most relevant logs, especially if these explain the root cause. For example: \nLogs from pod robusta-holmes:\n```\n<logs>```\n. Always embed the surroundding +/- 5 log lines to any relevant logs. ",
    "App or Infra?": "Explain whether the issue is more likely an infrastructure or an application level issue and why you think that.",
    "External links": "Provide links to external sources. Where to look when investigating this issue. For example provide links to relevant runbooks, etc. Add a short sentence describing each link.",
}


def get_output_format_for_investigation(sections: Dict[str, str]) -> Dict[str, Any]:
    properties = {}
    required_fields = []

    for title, description in sections.items():
        properties[title] = {"type": ["string", "null"], "description": description}
        required_fields.append(title)

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": required_fields,
        "properties": properties,
        "additionalProperties": False,
    }

    output_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "InvestigationResult",
            "schema": schema,
            "strict": False,
        },
    }

    return output_format


def combine_sections(sections: Any) -> str:
    if isinstance(sections, dict):
        content = ""
        for section_title, section_content in sections.items():
            if section_content:
                # content = content + f'\n# {" ".join(section_title.split("_")).title()}\n{section_content}'
                content = content + f"\n# {section_title}\n{section_content}\n"
        return content
    return f"{sections}"
