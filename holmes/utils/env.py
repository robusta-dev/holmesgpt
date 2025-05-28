import os
import re
import logging
from typing import Any, Optional
from pydantic import SecretStr


def get_env_replacement(value: str) -> Optional[str]:
    env_values = re.findall(r"{{\s*env\.([^\s]*)\s*}}", value)
    if not env_values:
        return None
    env_var_key = env_values[0].strip()
    if env_var_key not in os.environ:
        msg = f"ENV var replacement {env_var_key} does not exist for param: {value}"
        logging.error(msg)
        raise Exception(msg)

    return os.environ.get(env_var_key)


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
