# type: ignore
from tests.llm.utils.test_case_utils import HolmesTestCase
import pytest


def get_tags(test_case: HolmesTestCase):
    """
    Converts a list of tag strings into a list of pytest.mark objects.
    Example: ["smoke", "ui"] -> [pytest.mark.smoke, pytest.mark.ui]
    """
    if not test_case.tags:
        return []
    return [getattr(pytest.mark, tag) for tag in test_case.tags]


def add_tags_to_eval(test_case: HolmesTestCase):
    return pytest.param(test_case, marks=get_tags(test_case), id=test_case.id)
