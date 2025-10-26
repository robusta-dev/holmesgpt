from types import SimpleNamespace
from copy import deepcopy


def dict_to_obj(dict_data: dict) -> SimpleNamespace:
    """
    Convert a dictionary to a simple object with attributes corresponding to the dictionary keys.

    Example:
        >>> d = {"a": 1, "b": { "c": 2 }}
        >>> obj = dict_to_obj(d)
        >>> obj.a
        1
        >>> obj.b.c
        2
    """
    if not isinstance(dict_data, dict):
        raise ValueError("dict_data must be a dictionary")

    dict_to_convert = deepcopy(dict_data)
    for key, value in dict_to_convert.items():
        if isinstance(value, dict):
            dict_to_convert[key] = dict_to_obj(value)
        elif isinstance(value, list):
            for i in range(len(value)):
                if isinstance(value[i], dict):
                    value[i] = dict_to_obj(value[i])
                else:
                    value[i] = value[i]
        else:
            dict_to_convert[key] = value

    return SimpleNamespace(**dict_to_convert)
