from typing import Any

schema = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "Alert Explanation",
    "Investigation",
    "Conclusions and Possible Root causes",
    "Next Steps"
  ],
  "properties": {
    "Alert Explanation": {
      "type": ["string", "null"],
      "description": "1-2 sentences explaining the alert itself - note don't say \"The alert indicates a warning event related to a Kubernetes pod doing blah\" rather just say \"The pod XYZ did blah\" because that is what the user actually cares about"
    },
    "Investigation": {
      "type": ["string", "null"],
      "description": "what you checked and found"
    },
    "Conclusions and Possible Root causes": {
      "type": ["string", "null"],
      "description": "what conclusions can you reach based on the data you found? what are possible root causes (if you have enough conviction to say) or what uncertainty remains"
    },
    "Next Steps": {
      "type": ["string", "null"],
      "description": "what you would do next to troubleshoot this issue, any commands that could be run to fix it, or other ways to solve it (prefer giving precise bash commands when possible)"
    }
  },
  "additionalProperties": False
}

ExpectedInvestigationOutputFormat = { "type": "json_schema", "json_schema": { "name": "InvestigationResult", "schema": schema, "strict": False} }

def combine_sections(sections: Any) -> str:
    if isinstance(sections, dict):
        content = ''
        for section_title, section_content in sections.items():
            if section_content:
                # content = content + f'\n# {" ".join(section_title.split("_")).title()}\n{section_content}'
                content = content + f'\n# {section_title}\n{section_content}\n'
        return content
    return f"{sections}"
