from typing import Optional

from click import option
import pytest
from holmes.plugins.toolsets.bash.common.validators import validate_command_and_operations

ALLOWED_COMMANDS = {
    "list": {},
    "ls": {},
    "plugin": {
        "list":{}
    },
    "get": {
        "all": {},
        "hooks": {},
        "manifest": {},
        "notes": {},
        "values": {},
        "metadata": {},
    },
}

DENIED_COMMANDS = {
    # Repository management
    "repo": {
        "add": {},
        "remove": {},
    },
    # Chart packaging and publishing
    "create": {},
    # Plugin management
    "plugin": {
        "install": {},
        "uninstall": {},
        "update": {},
    },
}

@pytest.mark.parametrize(
    "command,options",
    [
        ("list", []),
        ("get", ["all"]),
        ("get", ["all", "foo"]),
        ("get", ["all", "--option"]),
        ("plugin", ["list"]),
    ]
)
def test_validate_command_and_operations(command:str, options:list[str]):
    validate_command_and_operations(command=command, options=options, allowed_commands=ALLOWED_COMMANDS, denied_commands=DENIED_COMMANDS)

@pytest.mark.parametrize(
    "command,options",
    [
        ("get", []),
        ("plugin", ["install"]),
        ("plugin", ["unknown"]),
        ("create", ["all"]),
    ]
)
def test_invalid_command_and_operations(command:str, options:list[str]):
    
    with pytest.raises(ValueError):
        validate_command_and_operations(command=command, options=options, allowed_commands=ALLOWED_COMMANDS, denied_commands=DENIED_COMMANDS)
