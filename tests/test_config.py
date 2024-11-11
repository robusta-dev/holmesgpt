
from typing import List
from holmes.core.tools import Toolset, get_matching_toolsets


def dummy_toolset(toolset_name:str):
    class DummyToolset(Toolset):
        def __init__(self, name):
            super().__init__(
                name = name,
                prerequisites = [
                ],
                tools = [],
            )
    return DummyToolset(toolset_name)

def test_matching_toolsets():
    toolsets:List[Toolset] = []

    toolsets.append(dummy_toolset("kubernetes/core"))
    toolsets.append(dummy_toolset("internet/core"))
    toolsets.append(dummy_toolset("findings/core"))

    matching_toolsets = get_matching_toolsets(toolsets, ["*/core"])

    assert matching_toolsets == toolsets
