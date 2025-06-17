import json
import os
import os.path
from datetime import date
from pathlib import Path
from typing import List, Optional, Pattern, Union

from pydantic import BaseModel, PrivateAttr

from holmes.utils.pydantic_utils import RobustaBaseConfig, load_model_from_file

THIS_DIR = os.path.abspath(os.path.dirname(__file__))

CATALOG_FILE = "catalog.json"


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


def load_runbooks_from_file(path: Union[str, Path]) -> List[Runbook]:
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


class RunbookCatalogEntry(BaseModel):
    """
    RunbookCatalogEntry contains metadata about a runbook
    Different from runbooks provided by Runbook class, this entry points to markdown file containing the runbook content.
    """

    Update_Date: date
    Description: str
    KeyWords: list[str]
    link: str


class RunbookCatalog(BaseModel):
    """
    RunbookCatalog is a collection of runbook entries, each entry contains metadata about the runbook.
    The correct runbook can be selected from the list by comparing the description with the user question.
    """

    catalog: List[RunbookCatalogEntry]


def load_catalog() -> Optional[RunbookCatalog]:
    dir_path = os.path.dirname(os.path.realpath(__file__))

    catalogPath = os.path.join(dir_path, CATALOG_FILE)
    if not os.path.isfile(catalogPath):
        return None

    with open(catalogPath) as file:
        catalog_dict = json.load(file)
        return RunbookCatalog(**catalog_dict)
    return None


def get_runbook_folder() -> str:
    return os.path.dirname(os.path.realpath(__file__))
