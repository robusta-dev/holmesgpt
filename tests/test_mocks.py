
import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner
from holmes.main import alertmanager
from holmes.plugins.destinations import DestinationType

@pytest.fixture
def mock_config():
    with patch('holmes.config') as MockConfig:
        config = MockConfig.return_value
        config.create_issue_investigator.return_value = Mock()
        config.create_alertmanager_source.return_value = Mock()
        yield config

@pytest.fixture
def mock_source(mock_config):
    source = mock_config.create_alertmanager_source.return_value
    source.fetch_issues.return_value = [
        Mock(name="Alert1"),
        Mock(name="Alert2")
    ]
    return source

def test_alertmanager(mock_config, mock_source):
    runner = CliRunner()


    mock_console = Mock()

    result = alertmanager(
        api_key="none",
        model="gpt-4o",

        alertmanager_url="http://example.com",
        alertmanager_username="none",
        alertmanager_password="none",
        alertmanager_alertname="TestAlert",
        alertmanager_label= ["severity=critical"],
        verbose=[],
        config_file=None,
        custom_toolsets=[],
        allowed_toolsets="*",
        custom_runbooks=[],
        max_steps=10,
        destination=DestinationType.CLI,

    )

    assert result == 0
