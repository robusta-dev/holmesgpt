from typing import List, Optional
from autoevals import Factuality, LLMClassifier
import os

classifier_model = os.environ.get("CLASSIFIER_MODEL", "gpt-4o-mini")

def evaluate_context_usage(context_items:List[str], output:Optional[str], input:Optional[str]):
    context = "\n- ".join(context_items)
    prompt_prefix = f"""
CONTEXT
-------
{context}


QUESTION
--------
{{{{input}}}}


ANSWER
------
{{{{output}}}}


Verify whether the ANSWER to the QUESTION refers to all items mentioned in the CONTEXT.
Then evaluate which of the following statement matches the closest and return the corresponding letter:

A. No item mentioned in the CONTEXT is mentioned in the ANSWER
B. Less than half of items present in the CONTEXT are mentioned in the ANSWER
C. More than half of items present iEvaluate which of the following descibes the OUTPUT best and return the related letter:n the CONTEXT are mentioned in the ANSWER
D. All items present in the CONTEXT are mentioned in the ANSWER
    """

    classifier = LLMClassifier(
        name="ContextPrecision",
        prompt_template=prompt_prefix,
        choice_scores={"A": 0, "B": 0.33, "C": 0.67, "D": 1},
        use_cot=True,
        model=classifier_model
    )
    return classifier(input=input, output=output, expected=None)


def evaluate_previous_logs_mention(output:Optional[str]):
    prompt_prefix = """

OUTPUT
======
{{output}}


Evaluate which of the following descibes the OUTPUT best and return the related letter:

A. OUTPUT makes no mention of "previous logs"
B. OUTPUT makes no mention logs
C. OUTPUT mentions "previous logs" and differentiate the anlysis with the "logs"
D. OUTPUT mentions both "logs" and "previous logs" but presents both as having the same meaning
    """

    classifier = LLMClassifier(
        name="LogsExplanation",
        prompt_template=prompt_prefix,
        choice_scores={"A": 1, "B": 1, "C": 0, "D": 1},
        use_cot=True,
        model=classifier_model
    )
    return classifier(input=None, output=output, expected=None)


def evaluate_correctness(expected_elements:List[str], output:Optional[str]):

    expected_elements_str = "\n- ".join(expected_elements)

    prompt_prefix = f"""
    You are evaluating the correctness of a response by a LLM. You must return a score between 0 and 1 that represents the correctness of the response/OUTPUT from the LLM.
    The correctness is defined by the amount of EXPECTED ELEMENTS present in the output. Correctness is 1 if all elements are presents and 0 if none are presents.
    The correctness score should be proportional to the number of EXPECTED ELEMENTS present in the OUTPUT.

    EXPECTED ELEMENTS
    =================

    - {expected_elements_str}

    OUTPUT
    ======

    {{output}}


    Return a score between 0 and 1 that is proportional to the number of EXPECTED ELEMENTS present in the OUTPUT.
        """

    classifier = LLMClassifier(
        name="Correctness",
        prompt_template=prompt_prefix,
        choice_scores={"A": 1, "B": 1, "C": 0, "D": 1},
        use_cot=True,
        model=classifier_model
    )
    return classifier(input=input, output=output, expected=None)


def evaluate_factuality(input:Optional[str], output:Optional[str], expected:Optional[str]):
    eval_factuality = Factuality()
    return eval_factuality(input=input, output=output, expected=expected)
