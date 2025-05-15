from typing import Optional
from autoevals import LLMClassifier
import os
from braintrust import Span, SpanTypeAttribute

classifier_model = os.environ.get("CLASSIFIER_MODEL", "gpt-4o")


def evaluate_context_usage(
    context_items: list[str],
    output: Optional[str],
    input: Optional[str],
    parent_span: Span,
):
    with parent_span.start_span(
        name="ContextPrecision", type=SpanTypeAttribute.SCORE
    ) as span:
        context = "\n- ".join(context_items)
        prompt_prefix = """
# CONTEXT

- {{expected}}

# QUESTION

{{input}}

# ANSWER

{{output}}


Verify whether the ANSWER to the QUESTION refers to all items mentioned in the CONTEXT.
Then evaluate which of the following statement matches the closest and return the corresponding letter:

A. No item mentioned in the CONTEXT is mentioned in the ANSWER
B. Less than half of items present in the CONTEXT are mentioned in the ANSWER
C. More than half of items present in the CONTEXT are mentioned in the ANSWER
D. All items present in the CONTEXT are mentioned in the ANSWER
"""
        classifier = LLMClassifier(
            name="ContextPrecision",
            prompt_template=prompt_prefix,
            choice_scores={"A": 0, "B": 0.33, "C": 0.67, "D": 1},
            use_cot=True,
            model=classifier_model,
        )
        eval_result = classifier(input=input, output=output, expected=context)
        span.log(
            input=prompt_prefix,
            output=eval_result.metadata.get("rationale", ""),
            expected=context,
            scores={
                "context": eval_result.score,
            },
            metadata=eval_result.metadata,
        )
        return eval_result


def evaluate_correctness(
    expected_elements: list[str], output: Optional[str], parent_span: Span
):
    with parent_span.start_span(
        name="Correctness", type=SpanTypeAttribute.SCORE
    ) as span:
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

        classifier = LLMClassifier(
            name="Correctness",
            prompt_template=prompt_prefix,
            choice_scores={"A": 1, "B": 0},
            use_cot=True,
            model=classifier_model,
        )

        correctness_eval = classifier(
            input=input, output=output, expected=expected_elements_str
        )

        span.log(
            input=prompt_prefix,
            output=correctness_eval.metadata.get("rationale", ""),
            expected=expected_elements_str,
            scores={
                "correctness": correctness_eval.score,
            },
            metadata=correctness_eval.metadata,
        )
        return correctness_eval


def evaluate_sections(
    sections: dict[str, bool], output: Optional[str], parent_span: Span
):
    with parent_span.start_span(name="Sections", type=SpanTypeAttribute.SCORE) as span:
        expected_sections = [
            section for section, expected in sections.items() if expected
        ]
        expected_sections_str = "\n".join(
            [f"- {section}" for section in expected_sections]
        )
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
            name="sections",
            prompt_template=prompt_prefix,
            choice_scores={"A": 0, "B": 1},
            use_cot=True,
            model=classifier_model,
        )
        correctness_eval = classifier(
            input=unexpected_sections_str, output=output, expected=expected_sections_str
        )

        span.log(
            input=prompt_prefix,
            output=correctness_eval.metadata.get("rationale", ""),
            expected=expected_sections_str,
            scores={
                "sections": correctness_eval.score,
            },
            metadata=correctness_eval.metadata,
        )

        return correctness_eval
