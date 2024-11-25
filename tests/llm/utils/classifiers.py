from typing import List
from autoevals import LLMClassifier

def get_context_classifier(context_items:List[str]):
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
C. More than half of items present in the CONTEXT are mentioned in the ANSWER
D. All items present in the CONTEXT are mentioned in the ANSWER
    """

    return LLMClassifier(
        name="ContextPrecision",
        prompt_template=prompt_prefix,
        choice_scores={"A": 0, "B": 0.33, "C": 0.67, "D": 1},
        use_cot=True,
    )


def get_logs_explanation_classifier():
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

    return LLMClassifier(
        name="LogsExplanation",
        prompt_template=prompt_prefix,
        choice_scores={"A": 1, "B": 1, "C": 0, "D": 1},
        use_cot=True,
    )
