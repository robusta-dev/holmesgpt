
from datetime import datetime
from typing import List

from autoevals import LLMClassifier


PROJECT="HolmesGPT"

def readable_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


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


Evaluate whether the ANSWER to the QUESTION refers to all items mentioned in the CONTEXT.
Then evaluate which of the following statement is match the closest and return the corresponding letter:

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
