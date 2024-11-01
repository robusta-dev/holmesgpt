import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase
from holmes.core.issue import Issue
from holmes.core.models import InvestigateRequest
from holmes.core.tool_calling_llm import ResourceInstructionDocument, ResourceInstructions, ToolCallResult
from rich.console import Console
from holmes.config import Config
from holmes.common.env_vars import (
    HOLMES_POST_PROCESSING_PROMPT
)


def test_case():

    investigate_request = InvestigateRequest(
        source="prometheus",
        title="starting container process caused",
        description="starting container process caused \"exec: \"mycommand\": executable file not found in $PATH\"",
        subject=dict(),
        context=dict(),
        source_instance_id="ApiRequest",
        include_tool_calls=True,
        include_tool_call_results=True,
        prompt_template="builtin://generic_investigation.jinja2",
    )
    raw_data = investigate_request.model_dump()

    runbook_url = "https://containersolutions.github.io/runbooks/posts/kubernetes/create-container-error/"
    resource_instructions = ResourceInstructions(
        instructions=[],
        documents=[ResourceInstructionDocument(url=runbook_url)]
    )
    console = Console()
    config = Config.load_from_env()
    ai = config.create_issue_investigator(
        console, allowed_toolsets='*'
    )

    issue = Issue(
        id="",
        name=investigate_request.title,
        source_type=investigate_request.source,
        source_instance_id=investigate_request.source_instance_id,
        raw=raw_data,
    )
    investigation = ai.investigate(
        issue=issue,
        prompt=investigate_request.prompt_template,
        console=console,
        post_processing_prompt=HOLMES_POST_PROCESSING_PROMPT,
        instructions=resource_instructions,
    )

    webpage_tool_calls = list(filter(lambda tool_call: tool_call.tool_name == "fetch_webpage", investigation.tool_calls))

    assert len(webpage_tool_calls) == 1
    assert runbook_url in webpage_tool_calls[0].description


    answer_relevancy_metric = AnswerRelevancyMetric(threshold=0.5)

    test_case = LLMTestCase(
        input="What if these shoes don't fit?",
        # Replace this with the actual output from your LLM application
        actual_output="We offer a 30-day full refund at no extra costs.",
        retrieval_context=["All customers are eligible for a 30 day full refund at no extra costs."]
    )
    assert_test(test_case, [answer_relevancy_metric])
