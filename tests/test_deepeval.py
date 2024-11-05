from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric

def test_answer_relevancy():

    test_case = LLMTestCase(
            input="How many pods do I have running on node ip-172-31-8-128.us-east-2.compute.internal?",
            actual_output="11 pods are running on node ip-172-31-8-128.us-east-2.compute.internal",
            expected_output="7 pods are running on ip-172-31-8-128.us-east-2.compute.internal",
            retrieval_context=["There are 7 pods running. The other pods on the node are not running"]
        )
    assert_test(test_case, [AnswerRelevancyMetric(1.0), FaithfulnessMetric(1.0)])
