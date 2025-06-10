from typing import Dict, List, Optional, Union
from autoevals import LLMClassifier, init
from braintrust.oai import wrap_openai
import openai
import os

classifier_model = os.environ.get("CLASSIFIER_MODEL", os.environ.get("MODEL", "gpt-4o"))
api_key = os.environ.get("AZURE_API_KEY", os.environ.get("OPENAI_API_KEY", None))
base_url = os.environ.get("AZURE_API_BASE", None)
api_version = os.environ.get("AZURE_API_VERSION", None)

if base_url:
    client = openai.AzureOpenAI(
        azure_endpoint=base_url,
        azure_deployment=classifier_model,
        api_version=api_version,
        api_key=api_key,
    )
    wrapped = wrap_openai(client)
    init(wrapped)  # type: ignore


def evaluate_correctness(
    expected_elements: Union[str, List[str]],
    output: Optional[str],
    evaluation_type: str = "strict",
):
    if isinstance(expected_elements, str):
        expected_elements = [expected_elements]
    expected_elements_str = "\n- ".join(expected_elements)

    prompt_prefix = """
You are evaluating the correctness of an OUTPUT given by a LLM. You must return a score that
represents the correctness of that OUTPUT.

The correctness is defined by the presence of EXPECTED ELEMENTS in the OUTPUT.
Make a judgement call whether each ELEMENT sufficiently matches the OUTPUT. ELEMENTS do
not need to appear verbatim or be a perfect match but their essence should be
present in the whole OUTPUT, even if it spans multiple sentences.

# EXPECTED ELEMENTS

- {{expected}}

# OUTPUT

{{output}}


Return a choice based on the number of EXPECTED ELEMENTS present in the OUTPUT.
Possible choices:
    - A: All elements are presents
    - B: Either no element is present or only some but not all elements are present
    """

    if evaluation_type == "loose":
        prompt_prefix = """
You are evaluating the correctness of an OUTPUT given by a LLM. You must return a score that
represents the correctness of that OUTPUT.

The correctness is defined by the presence of EXPECTED in the OUTPUT.
Make a judgement call whether each ELEMENT sufficiently matches the OUTPUT. ELEMENTS do
not need to appear verbatim or be a perfect match but their essence should be
present in the whole OUTPUT, even if it spans multiple sentences.

# EXPECTED

{{expected}}

# OUTPUT

{{output}}


Return a choice based on the number of EXPECTED presence in the OUTPUT.
Possible choices:
    - A: The OUTPUT reasonably matches the EXPECTED content
    - B: The OUTPUT does not match the EXPECTED content
    """

    classifier = LLMClassifier(
        name="Correctness",
        prompt_template=prompt_prefix,
        choice_scores={"A": 1, "B": 0},
        use_cot=True,
        model=classifier_model,
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
    )
    return classifier(input=input, output=output, expected=expected_elements_str)


def evaluate_sections(sections: Dict[str, bool], output: Optional[str]):
    expected_sections = [section for section, expected in sections.items() if expected]
    expected_sections_str = "\n".join([f"- {section}" for section in expected_sections])
    if not expected_sections_str:
        expected_sections_str = "<No section is expected>"

    unexpected_sections = [
        section for section, expected in sections.items() if not expected
    ]
    unexpected_sections_str = "\n".join(
        [f"- {section}" for section in unexpected_sections]
    )
    if not unexpected_sections_str:
        unexpected_sections_str = "<No element>"

    prompt_prefix = """
You are evaluating the correctness of an OUTPUT given by a LLM. You must return a score that
represents the correctness of that OUTPUT.

The LLM output is expected to be split into sections. Typically each section is represented by a markdown title `# <section title>`.
Some sections are expected and should be populated in the output. Some sections are unexpected and should not be present in the outpout
(i.e. there is no such title: `# <unexpected section`)

If there are <No element> in EXPECTED SECTIONS assume the OUTPUT has all appropriate EXPECTED SECTIONS.
If there are <No element> in UNEXPECTED SECTIONS assume the OUTPUT has no UNEXPECTED SECTIONS.


# EXPECTED SECTIONS

{{expected}}


# UNEXPECTED SECTIONS

{{input}}


# OUTPUT

{{output}}


Return a choice based on the number of EXPECTED ELEMENTS present in the OUTPUT.
Possible choices:
    A. One or more of the EXPECTED SECTIONS is missing and one or more of the UNEXPECTED SECTIONS is present
    B. All EXPECTED SECTIONS are present in the OUTPUT and no UNEXPECTED SECTIONS is present in the output
    """

    classifier = LLMClassifier(
        name="Correctness",
        prompt_template=prompt_prefix,
        choice_scores={"A": 0, "B": 1},
        use_cot=True,
        model=classifier_model,
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
    )
    return classifier(
        input=unexpected_sections_str, output=output, expected=expected_sections_str
    )
