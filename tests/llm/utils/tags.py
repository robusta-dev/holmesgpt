<<<<<<< Updated upstream
# type: ignore
=======
>>>>>>> Stashed changes
from tests.llm.utils.mock_utils import HolmesTestCase
import pytest


<<<<<<< Updated upstream
def get_tags(test_case: HolmesTestCase):
=======
def get_tags(test_case:HolmesTestCase):
>>>>>>> Stashed changes
    """
    Converts a list of tag strings into a list of pytest.mark objects.
    Example: ["smoke", "ui"] -> [pytest.mark.smoke, pytest.mark.ui]
    """
    if not test_case.tags:
        return []
    return [getattr(pytest.mark, tag) for tag in test_case.tags]

<<<<<<< Updated upstream

def add_tags_to_eval(experiment_name: str, test_case: HolmesTestCase):
    return pytest.param(
        experiment_name, test_case, marks=get_tags(test_case), id=test_case.id
    )
=======
def add_tags_to_eval(experiment_name:str, test_case:HolmesTestCase):

    return pytest.param(
        experiment_name,
        test_case,
        marks=get_tags(test_case), 
        id=experiment_name
    )

>>>>>>> Stashed changes
