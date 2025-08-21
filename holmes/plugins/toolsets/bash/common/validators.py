import argparse
import re
from typing import Union


def regex_validator(field_name: str, pattern: Union[str, re.Pattern]):
    def check_regex(arg_value):
        if not re.match(pattern, arg_value):
            raise argparse.ArgumentTypeError(f"invalid {field_name} value")
        return arg_value

    return check_regex


def whitelist_validator(field_name: str, whitelisted_values: set[str]):
    def validate_value(value: str) -> str:
        if value not in whitelisted_values:
            whitelisted_values_str = ", ".join(whitelisted_values)
            raise argparse.ArgumentTypeError(
                f"Invalid {field_name} format: '{value}'. Must be one of [{whitelisted_values_str}]"
            )
        return value

    return validate_value



def validate_command_and_operations(command: str, options: list[str], allowed_commands:dict[str, dict], denied_commands:dict[str, dict]) -> None:
    """Validate that the Helm command and operation combination is safe."""
    # Check if command itself is a blocked operation first (top-level commands like "install")

    command_str_for_error_message = command

    denied_command = denied_commands.get(command, None)
    if denied_command == {}:
        raise ValueError(
            f"Command is blocked: {command_str_for_error_message}"
        )
    elif denied_command is not None:
        for option in options:
            command_str_for_error_message += " " + option
            denied_command = denied_command.get(option, None)
            if denied_command is None:
                break
            elif denied_command == {}:
                raise ValueError(
                    f"Command is blocked: {command_str_for_error_message}"
                )
            
    allowed_command = allowed_commands.get(command, None)
    if allowed_command == {}:
        return
    elif allowed_command is not None:
        
        for option in options:
            command_str_for_error_message += " " + option
            allowed_command = allowed_command.get(option, None)
            if allowed_command is None:
                raise ValueError(
                    f"Command '{command_str_for_error_message}' is not in the allowlist"
                )
            elif allowed_command == {}:
                return


    raise ValueError(
        f"Command '{command_str_for_error_message}' is not in the allowlist"
    )