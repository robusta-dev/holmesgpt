import logging

from holmes.common.env_vars import HOLMES_POST_PROCESSING_PROMPT
from holmes.config import Config
from holmes.core.investigation_structured_output import process_response_into_sections
from holmes.core.issue import Issue
from holmes.core.models import InvestigateRequest, InvestigationResult
from holmes.core.supabase_dal import SupabaseDal
from holmes.utils.robusta import load_robusta_api_key


def investigate_issues(
    investigate_request: InvestigateRequest, dal: SupabaseDal, config: Config
):
    load_robusta_api_key(dal=dal, config=config)
    context = dal.get_issue_data(investigate_request.context.get("robusta_issue_id"))


    resource_instructions = dal.get_resource_instructions(
        "alert", investigate_request.context.get("issue_type")
    )
    global_instructions = dal.get_global_instructions_for_account()

    raw_data = investigate_request.model_dump()
    if context:
        raw_data["extra_context"] = context

    ai = config.create_issue_investigator(dal=dal)

    issue = Issue(
        id=context["id"] if context else "",
        name=investigate_request.title,
        source_type=investigate_request.source,
        source_instance_id=investigate_request.source_instance_id,
        raw=raw_data,
    )

    investigation = ai.investigate(
        issue,
        prompt=investigate_request.prompt_template,
        post_processing_prompt=HOLMES_POST_PROCESSING_PROMPT,
        instructions=resource_instructions,
        global_instructions=global_instructions,
        sections=investigate_request.sections,
    )

    (text_response, sections) = process_response_into_sections(investigation.result)

    logging.debug(f"text response: {text_response}")
    return InvestigationResult(
        analysis=text_response,
        sections=sections,
        tool_calls=investigation.tool_calls or [],
        instructions=investigation.instructions,
    )
