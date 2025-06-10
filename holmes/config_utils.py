import logging
import os
import os.path
from typing import Any, Optional
from pydantic import SecretStr
import re


def get_env_replacement(value: str) -> Optional[str]:
    env_patterns = re.findall(r"{{\s*env\.([^}]*)\s*}}", value)

    result = value

    # Replace env patterns with their values or raise exception
    for env_var_key in env_patterns:
        env_var_key = env_var_key.strip()
        pattern_regex = r"{{\s*env\." + re.escape(env_var_key) + r"\s*}}"
        if env_var_key in os.environ:
            replacement = os.environ[env_var_key]
        else:
            msg = f"ENV var replacement {env_var_key} does not exist"
            logging.error(msg)
            raise Exception(msg)
        result = re.sub(pattern_regex, replacement, result)

    return result


def replace_env_vars_values(values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        if isinstance(value, str):
            env_var_value = get_env_replacement(value)
            if env_var_value:
                values[key] = env_var_value
        elif isinstance(value, SecretStr):
            env_var_value = get_env_replacement(value.get_secret_value())
            if env_var_value:
                values[key] = SecretStr(env_var_value)
        elif isinstance(value, dict):
            replace_env_vars_values(value)
        elif isinstance(value, list):
            # can be a list of strings
            values[key] = [
                replace_env_vars_values(iter)
                if isinstance(iter, dict)
                else get_env_replacement(iter)
                if isinstance(iter, str)
                else iter
                for iter in value
            ]
    return values
