from holmes.config import Config


def test_config_default_none():
    """Test that default value is None for backward compatibility"""
    config = Config()
    assert config.allowed_builtin_toolsets is None


def test_config_parse_comma_separated(tmp_path):
    """Test parsing comma-separated string to list through actual config loading"""
    # Create a minimal config file - can be empty since we're testing CLI option parsing
    config_file = tmp_path / "config.yaml"
    config_content = """
# Empty config file - testing CLI argument parsing
model: "gpt-4o"
"""
    config_file.write_text(config_content)

    # Pass the comma-separated string as a CLI kwarg to test the parsing logic
    config = Config.load_from_file(
        config_file, allowed_builtin_toolsets="kubernetes/core,prometheus/core"
    )

    # Assert that the parsing worked correctly
    assert config.allowed_builtin_toolsets == ["kubernetes/core", "prometheus/core"]


def test_config_handle_whitespace(tmp_path):
    """Test handling of whitespace and empty strings"""
    # Create a minimal config file for testing CLI argument parsing
    config_file = tmp_path / "config.yaml"
    config_content = """
# Test config for whitespace handling
model: "gpt-4o"
"""
    config_file.write_text(config_content)

    test_cases = [
        ("kubernetes/core, prometheus/core", ["kubernetes/core", "prometheus/core"]),
        ("kubernetes/core,  ,prometheus/core", ["kubernetes/core", "prometheus/core"]),
        ("  kubernetes/core  ", ["kubernetes/core"]),
        ("", []),
    ]

    for input_str, expected in test_cases:
        # Use the public API to test the parsing logic
        config = Config.load_from_file(config_file, allowed_builtin_toolsets=input_str)
        assert config.allowed_builtin_toolsets == expected


def test_config_backward_compatibility():
    """Test that existing config loading works unchanged"""
    config = Config()
    assert hasattr(config, "allowed_builtin_toolsets")
    assert config.allowed_builtin_toolsets is None


def test_config_load_from_file_with_allowed_toolsets():
    """Test that load_from_file correctly parses the allowed_builtin_toolsets option"""
    # Test with comma-separated string
    config = Config.load_from_file(
        None, allowed_builtin_toolsets="kubernetes/core,prometheus/core"
    )
    assert config.allowed_builtin_toolsets == ["kubernetes/core", "prometheus/core"]


def test_config_load_from_file_with_whitespace():
    """Test that load_from_file handles whitespace correctly"""
    # Test with whitespace and empty strings
    config = Config.load_from_file(
        None, allowed_builtin_toolsets="kubernetes/core, prometheus/core,  "
    )
    assert config.allowed_builtin_toolsets == ["kubernetes/core", "prometheus/core"]


def test_config_load_from_file_with_empty_string():
    """Test that load_from_file handles empty string correctly"""
    config = Config.load_from_file(None, allowed_builtin_toolsets="")
    assert config.allowed_builtin_toolsets == []


def test_config_load_from_file_without_option():
    """Test that load_from_file works when option is not provided"""
    config = Config.load_from_file(None)
    assert config.allowed_builtin_toolsets is None


def test_config_load_from_file_with_none():
    """Test that load_from_file handles None value correctly"""
    config = Config.load_from_file(None, allowed_builtin_toolsets=None)
    assert config.allowed_builtin_toolsets is None


def test_config_load_from_file_single_toolset():
    """Test parsing single toolset name"""
    config = Config.load_from_file(None, allowed_builtin_toolsets="kubernetes/core")
    assert config.allowed_builtin_toolsets == ["kubernetes/core"]


def test_config_load_from_file_complex_names():
    """Test parsing complex toolset names with special characters"""
    config = Config.load_from_file(
        None, allowed_builtin_toolsets="aws/ec2,grafana/loki,kubernetes/core"
    )
    assert config.allowed_builtin_toolsets == [
        "aws/ec2",
        "grafana/loki",
        "kubernetes/core",
    ]


def test_config_direct_assignment():
    """Test that the field can be assigned directly"""
    config = Config(allowed_builtin_toolsets=["kubernetes/core", "prometheus/core"])
    assert config.allowed_builtin_toolsets == ["kubernetes/core", "prometheus/core"]


def test_config_field_type_checking():
    """Test that the field accepts correct types"""
    # Test with None
    config = Config(allowed_builtin_toolsets=None)
    assert config.allowed_builtin_toolsets is None

    # Test with empty list
    config = Config(allowed_builtin_toolsets=[])
    assert config.allowed_builtin_toolsets == []

    # Test with list of strings
    config = Config(allowed_builtin_toolsets=["test/toolset"])
    assert config.allowed_builtin_toolsets == ["test/toolset"]
