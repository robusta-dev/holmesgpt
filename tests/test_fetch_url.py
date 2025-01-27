import os
import re
from typing import List
from pydantic import BaseModel
import pytest
from pathlib import Path

from holmes.core.tools import ToolExecutor
from holmes.plugins.toolsets.internet import InternetToolset, html_to_markdown

THIS_DIR = os.path.dirname(__file__)
FIXTURES_DIR = os.path.join(THIS_DIR, 'fixtures', 'test_fetch_url')


TEST_URL = "https://www.example.com"
EXPECTED_TEST_RESULT = """
Example Domain

Example Domain
==============

This domain is for use in illustrative examples in documents. You may use this
 domain in literature without prior coordination or asking for permission.

[More information...](https://www.iana.org/domains/example)
""".strip()

def read_file(file_path:Path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read().strip()

def parse_fixture_id(file_name:str) -> str:
    match = re.match(r'fixture(\d+)', file_name)
    if match:
        # Extract the number
        return match.group(1)
    else:
        raise Exception(f"Could not find fixture id in filename {file_name}")

class Fixture(BaseModel):
    id: str
    input: str
    expected_output: str


def load_all_fixtures() -> List[Fixture]:
    """
    Load the fixtures in the fixtures folder by pair fixtureX_input.html with fixtureX_output.md
    to feed the test
    """
    fixtures_dir = Path(FIXTURES_DIR)
    input_files = sorted([f for f in fixtures_dir.glob('fixture*.html')])
    test_cases = []

    for input_file in input_files:
        number = parse_fixture_id(input_file.stem)
        output_file = fixtures_dir / f'fixture{number}_output.md'

        if output_file.exists():
            input_content = read_file(input_file)
            output_content = read_file(output_file)
            test_cases.append(Fixture(id=number, input=input_content, expected_output=output_content))

    assert len(test_cases) > 0
    return test_cases

def idfn(val):
    if isinstance(val, Fixture):
        return f"Fixture #{val.id}"
    else:
        return str(val)

@pytest.mark.parametrize("fixture", load_all_fixtures(),ids=idfn)
def test_html_to_markdown(fixture:Fixture):
    actual_output = html_to_markdown(fixture.input)
    print(actual_output)
    assert actual_output.strip() == fixture.expected_output.strip()

def test_fetch_webpage():
    toolset = InternetToolset()
    tool_executor = ToolExecutor(toolsets=[toolset])
    fetch_webpage_tool = tool_executor.get_tool_by_name('fetch_webpage')
    assert fetch_webpage_tool
    actual_output = fetch_webpage_tool.invoke({"url": TEST_URL})
    print(actual_output)
    assert actual_output.strip() == EXPECTED_TEST_RESULT
