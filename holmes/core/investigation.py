from holmes.common.env_vars import HOLMES_POST_PROCESSING_PROMPT
from holmes.config import Config
from holmes.core.investigation_structured_output import process_response_into_sections
from holmes.core.issue import Issue
from holmes.core.models import InvestigateRequest, InvestigationResult
from holmes.core.supabase_dal import SupabaseDal
from holmes.utils.robusta import load_robusta_api_key
import logging

from holmes.core.investigation_structured_output import (
    DEFAULT_SECTIONS,
    REQUEST_STRUCTURED_OUTPUT_FROM_LLM,
    get_output_format_for_investigation,
)

from holmes.plugins.prompts import load_and_render_prompt

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

    return InvestigationResult(
        analysis=text_response,
        sections=sections,
        tool_calls=investigation.tool_calls or [],
        instructions=investigation.instructions,
    )


def get_investigation_context(investigate_request: InvestigateRequest, dal: SupabaseDal, config: Config):
    load_robusta_api_key(dal=dal, config=config)
    ai = config.create_issue_investigator(dal=dal)

    raw_data = investigate_request.model_dump()
    context = dal.get_issue_data(investigate_request.context.get("robusta_issue_id"))
    if context:
        raw_data["extra_context"] = context

    issue = Issue(
        id=context["id"] if context else "",
        name=investigate_request.title,
        source_type=investigate_request.source,
        source_instance_id=investigate_request.source_instance_id,
        raw=raw_data,
    )

    runbooks = ai.runbook_manager.get_instructions_for_issue(issue)

    instructions = dal.get_resource_instructions(
        "alert", investigate_request.context.get("issue_type")
    )
    if instructions is not None and instructions.instructions:
        runbooks.extend(instructions.instructions)
    if instructions is not None and len(instructions.documents) > 0:
        docPrompts = []
        for document in instructions.documents:
            docPrompts.append(
                f"* fetch information from this URL: {document.url}\n"
            )
        runbooks.extend(docPrompts)


    # This section is about setting vars to request the LLM to return structured output.
    # It does not mean that Holmes will not return structured sections for investigation as it is
    # capable of splitting the markdown into sections
    request_structured_output_from_llm = True
    response_format = None
    sections = investigate_request.sections
    if not sections or len(sections) == 0:
        # If no sections are passed, we will not ask the LLM for structured output
        sections = DEFAULT_SECTIONS
        request_structured_output_from_llm = False
        logging.info(
            "No section received from the client. Default sections will be used."
        )
    elif ai.llm.model and ai.llm.model.startswith("bedrock"):
        # Structured output does not work well with Bedrock Anthropic Sonnet 3.5 through litellm
        request_structured_output_from_llm = False

    if not REQUEST_STRUCTURED_OUTPUT_FROM_LLM:
        request_structured_output_from_llm = False

    if request_structured_output_from_llm:
        response_format = get_output_format_for_investigation(sections)
        logging.info("Structured output is enabled for this request")
    else:
        logging.info("Structured output is disabled for this request")

    system_prompt = load_and_render_prompt(
        investigate_request.prompt_template,
        {
            "issue": issue,
            "sections": sections,
            "structured_output": request_structured_output_from_llm,
        },
    )

    user_prompt = ""
    if runbooks:
        for runbook_str in runbooks:
            user_prompt += f"* {runbook_str}\n"

        user_prompt = f'My instructions to check \n"""{user_prompt}"""'

    global_instructions = dal.get_global_instructions_for_account()
    if (
        global_instructions
        and global_instructions.instructions
        and len(global_instructions.instructions[0]) > 0
    ):
        user_prompt += f"\n\nGlobal Instructions (use only if relevant): {global_instructions.instructions[0]}\n"

    user_prompt = f"{user_prompt}\n This is context from the issue {issue.raw}"


    return ai, system_prompt, user_prompt, response_format, sections