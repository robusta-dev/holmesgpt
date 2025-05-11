import os
import os.path
from pathlib import Path
from typing import List, Optional, Pattern

from pydantic import BaseModel, PrivateAttr

from holmes.utils.pydantic_utils import RobustaBaseConfig, load_model_from_file

THIS_DIR = os.path.abspath(os.path.dirname(__file__))


class IssueMatcher(RobustaBaseConfig):
    issue_id: Optional[Pattern] = None  # unique id
    issue_name: Optional[Pattern] = None  # not necessary unique
    source: Optional[Pattern] = None


class Runbook(RobustaBaseConfig):
    match: IssueMatcher
    instructions: str

    _path = PrivateAttr()

    def set_path(self, path: str):
        self._path = path

    def get_path(self) -> str:
        return self._path


class ListOfRunbooks(BaseModel):
    runbooks: List[Runbook]


def load_runbooks_from_file(path: str | Path) -> List[Runbook]:
    data: ListOfRunbooks = load_model_from_file(ListOfRunbooks, file_path=path)  # type: ignore
    for runbook in data.runbooks:
        runbook.set_path(path)  # type: ignore
    return data.runbooks


def load_builtin_runbooks() -> List[Runbook]:
    all_runbooks = []
    for filename in os.listdir(THIS_DIR):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(THIS_DIR, filename)
        all_runbooks.extend(load_runbooks_from_file(path))
    return all_runbooks
