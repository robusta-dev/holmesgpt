import logging
from typing import Any, Dict, Optional, Tuple, Union
import json

from pydantic import RootModel

InputSectionsDataType = Dict[str, str]

OutputSectionsDataType = Optional[Dict[str, Union[str, None]]]

SectionsData = RootModel[OutputSectionsDataType]

DEFAULT_SECTIONS: InputSectionsDataType = {
    "Alert Explanation": '1-2 sentences explaining the alert itself - note don\'t say "The alert indicates a warning event related to a Kubernetes pod doing blah" rather just say "The pod XYZ did blah" because that is what the user actually cares about',
    "Investigation": "What you checked and found",
    "Conclusions and Possible Root causes": "What conclusions can you reach based on the data you found? what are possible root causes (if you have enough conviction to say) or what uncertainty remains. Don't say root cause but 'possible root causes'. Be clear to distinguish between what you know for certain and what is a possible explanation",
    "Next Steps": "What you would do next to troubleshoot this issue, any commands that could be run to fix it, or other ways to solve it (prefer giving precise bash commands when possible)",
    "Related logs": "Truncate and share the most relevant logs, especially if these explain the root cause. For example: \nLogs from pod robusta-holmes:\n```\n<logs>```\n. Always embed the surroundding +/- 5 log lines to any relevant logs. ",
    "App or Infra?": "Explain whether the issue is more likely an infrastructure or an application level issue and why you think that.",
    "External links": "Provide links to external sources. Where to look when investigating this issue. For example provide links to relevant runbooks, etc. Add a short sentence describing each link.",
}


def get_output_format_for_investigation(
    sections: InputSectionsDataType,
) -> Dict[str, Any]:
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


def combine_sections(sections: Dict) -> str:
    content = ""
    for section_title, section_content in sections.items():
        if section_content:
            content = content + f"\n# {section_title}\n{section_content}\n"
    return content


def process_response_into_sections(response: Any) -> Tuple[str, OutputSectionsDataType]:
    if isinstance(response, dict):
        # No matter if the result is already structured, we want to go through the code below to validate the JSON
        response = json.dumps(response)

    if not isinstance(response, str):
        # if it's not a string, we make it so as it'll be parsed later
        response = str(response)

    if response.startswith("```json\n") and response.endswith("\n```"):
        try:
            parsed = json.loads(response[8:-3]) # if this parses as json, set the response as that.
            if isinstance(parsed, dict):
                logging.warning("LLM did not return structured data")
                response = response[8:-3]
        except Exception:
            pass


    try:
        parsed_json = json.loads(response)
        # TODO: force dict values into a string would make this more resilient as SectionsData only accept none/str as values
        sections = SectionsData(root=parsed_json).root
        if sections:
            combined = combine_sections(sections)
            return (combined, sections)
    except Exception:
        pass

    return (response, None)
