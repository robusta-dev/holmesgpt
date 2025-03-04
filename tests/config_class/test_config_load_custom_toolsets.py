import yaml
import pytest

from holmes.config import Config


# class DummyToolsetYamlFromConfig to bypass actual validations and test only load_custom_toolsets_config
class DummyToolsetYamlFromConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.config = kwargs.get("config", None)

    def set_path(self, path):
        self.path = path


@pytest.fixture(autouse=True)
def patch_toolset_yaml(monkeypatch):
    monkeypatch.setattr(
        "holmes.config.ToolsetYamlFromConfig", DummyToolsetYamlFromConfig
    )


def test_load_custom_toolsets_config_valid(tmp_path):
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {"toolsets": {"dummy_tool": {"enabled": True, "config": {"key": "value"}}}}
    custom_file.write_text(yaml.dump(data))

    config = Config(custom_toolsets=[str(custom_file)])
    result = config.load_custom_toolsets_config()

    assert isinstance(result, list)
    assert len(result) == 1
    tool = result[0]
    assert tool.name == "dummy_tool"
    assert str(getattr(tool, "path", None)) == str(custom_file)


def test_load_custom_toolsets_config_missing_toolsets(tmp_path, monkeypatch):
    custom_file = tmp_path / "custom_toolset.yaml"
    data = {"not_toolsets": {}}
    custom_file.write_text(yaml.dump(data))

    monkeypatch.setattr(
        "holmes.config.CUSTOM_TOOLSET_LOCATION", str(tmp_path / "nonexistent.yaml")
    )

    config = Config(custom_toolsets=[str(custom_file)])
    result = config.load_custom_toolsets_config()

    assert result == []


def test_load_custom_toolsets_config_invalid_yaml(tmp_path, monkeypatch):
    custom_file = tmp_path / "custom_toolset.yaml"
    custom_file.write_text("::::")

    monkeyatch_value = str(tmp_path / "nonexistent.yaml")
    monkeypatch.setattr("holmes.config.CUSTOM_TOOLSET_LOCATION", monkeyatch_value)

    config = Config(custom_toolsets=[str(custom_file)])
    result = config.load_custom_toolsets_config()

    assert result == []


def test_load_custom_toolsets_config_empty_file(tmp_path, monkeypatch):
    custom_file = tmp_path / "custom_toolset.yaml"
    custom_file.write_text("")

    monkeypatch.setattr(
        "holmes.config.CUSTOM_TOOLSET_LOCATION", str(tmp_path / "nonexistent.yaml")
    )

    config = Config(custom_toolsets=[str(custom_file)])
    result = config.load_custom_toolsets_config()

    assert result == []


def test_load_custom_toolsets_config_fallback(tmp_path, monkeypatch):
    fallback_file = tmp_path / "fallback.yaml"
    data = {
        "toolsets": {
            "fallback_tool": {"enabled": False, "config": {"fallback": "value"}}
        }
    }
    fallback_file.write_text(yaml.dump(data))

    monkeypatch.setattr("holmes.config.CUSTOM_TOOLSET_LOCATION", str(fallback_file))

    config = Config(custom_toolsets=[])
    result = config.load_custom_toolsets_config()

    assert isinstance(result, list)
    assert len(result) == 1
    tool = result[0]
    assert tool.name == "fallback_tool"
    assert getattr(tool, "path", None) == str(fallback_file)


def test_load_toolsets_config_old_format():
    config = Config()
    old_format_data = [
        {
            "name": "aws/security",
            "prerequisites": [{"command": "aws sts get-caller-identity"}],
            "tools": [
                {
                    "name": "aws_cloudtrail_event_lookup",
                    "description": "Fetches events from AWS CloudTrail",
                    "command": "aws cloudtrail lookup-events",
                }
            ],
        }
    ]

    with pytest.raises(ValueError, match="Old toolset config format detected"):
        config.load_toolsets_config(old_format_data, "dummy_path")


def test_load_toolsets_config_multiple_old_format_toolsets():
    config = Config()
    old_format_data = [
        {
            "name": "aws/security",
            "prerequisites": [{"command": "aws sts get-caller-identity"}],
            "tools": [
                {
                    "name": "aws_cloudtrail_event_lookup",
                    "description": "Fetches events from AWS CloudTrail",
                    "command": "aws cloudtrail lookup-events",
                }
            ],
        },
        {
            "name": "kubernetes/logs",
            "tools": [
                {
                    "name": "kubectl_logs",
                    "description": "Fetch Kubernetes logs",
                    "command": "kubectl logs",
                }
            ],
        },
    ]

    with pytest.raises(ValueError, match="Old toolset config format detected"):
        config.load_toolsets_config(old_format_data, "dummy_path")
