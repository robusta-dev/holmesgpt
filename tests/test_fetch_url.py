import os
import re
import pytest
from pathlib import Path

THIS_DIR = os.path.dirname(__file__)
FIXTURES_DIR = os.path.join(THIS_DIR, 'fixtures')

# Import your function here
from holmes.plugins.toolsets.internet import html_to_markdown

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read().strip()

def parse_fixture_id(file_name:str) -> str:
    match = re.match(r'fixture(\d+)', file_name)
    if match:
        # Extract the number
        return match.group(1)
    else:
        raise Exception(f"Could not find fixture id in filename {file_name}")

def load_all_fixtures():
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
            test_cases.append((input_content, output_content))

    return test_cases

@pytest.mark.parametrize("input,expected_output", load_all_fixtures())
def test_html_to_markdown(input, expected_output):
    actual_output = html_to_markdown(input)
    assert actual_output.strip() == expected_output.strip()
