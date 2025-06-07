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
