
import json
import braintrust
from typing_extensions import Dict
import yaml
import logging
import os
import re
from pathlib import Path
from typing import Generic, List, Optional, TypeVar, Union, cast

from pydantic import BaseModel, TypeAdapter
from holmes.core.models import InvestigateRequest
from holmes.core.tool_calling_llm import ResourceInstructions
from tests.llm.utils.constants import AUTO_GENERATED_FILE_SUFFIX
from tests.llm.utils.mock_toolset import MockMetadata, ToolMock
from tests.llm.utils.mock_utils import AskHolmesTestCase, HolmesTestCase, InvestigateTestCase

def find_dataset_row_by_test_case(dataset:braintrust.Dataset, test_case:HolmesTestCase):
    for row in dataset:
        if row.get("metadata", {}).get("id") == test_case.id:
            return row
    return None


def upload_dataset(
    test_cases:Union[List[AskHolmesTestCase], List[InvestigateTestCase]],
    project_name:str,
    dataset_name:str):

    dataset = braintrust.init_dataset(project=project_name, name=dataset_name)
    for test_case in test_cases:

        input = ""
        if isinstance(test_case, AskHolmesTestCase):
            input = test_case.user_prompt
        elif isinstance(test_case, InvestigateTestCase):
            input = test_case.investigate_request
        else:
            raise Exception("Unsupported test case class")

        row = find_dataset_row_by_test_case(dataset, test_case)

        if row:
            dataset.update(
                id=test_case.id,
                input=input,
                expected=test_case.expected_output,
                metadata=test_case.model_dump(),
                tags=[],
            )
        else:
            dataset.insert(
                id=test_case.id,
                input=input,
                expected=test_case.expected_output,
                metadata=test_case.model_dump(),
                tags=[],
            )
        logging.info("Inserted dataset record with id", id)

    logging.info(dataset.summarize())
