from holmes.utils.dict_utils import dict_to_obj
import pytest


def test_dict_to_obj():
    d = {"a": 1, "b": {"c": 2}}
    obj = dict_to_obj(d)
    assert obj.a == 1
    assert obj.b.c == 2


def test_invalid_input():
    with pytest.raises(ValueError):
        dict_to_obj(1)
