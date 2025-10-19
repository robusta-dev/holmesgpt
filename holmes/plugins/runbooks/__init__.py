import json
import logging
import os
import os.path
from datetime import date
from pathlib import Path
from typing import List, Optional, Pattern, Union, Tuple, TYPE_CHECKING
import yaml
from pydantic import BaseModel, PrivateAttr

from holmes.utils.pydantic_utils import RobustaBaseConfig, load_model_from_file

if TYPE_CHECKING:
    from holmes.core.supabase_dal import SupabaseDal

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_RUNBOOK_SEARCH_PATH = THIS_DIR

CATALOG_FILE = "catalog.json"


class RobustaRunbookInstruction(BaseModel):
    id: str
    symptom: str
    title: str
    instruction: Optional[str] = None

    class _LiteralDumper(yaml.SafeDumper):
        pass

    @staticmethod
    def _repr_str(dumper, s: str):
        s = s.replace("\\n", "\n")
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", s, style="|" if "\n" in s else None
        )

    # register representer (PyYAML API)
    _LiteralDumper.add_representer(str, _repr_str)  # type: ignore

    def to_list_string(self) -> str:
        return f"{self.id}"

    def to_prompt_string(self) -> str:
        return f"id='{self.id}' | title='{self.title}' | symptom='{self.symptom}'"

    def pretty(self) -> str:
        try:
            data = self.model_dump(exclude_none=True)  # pydantic v2
        except AttributeError:
            data = self.dict(exclude_none=True)  # pydantic v1
        return yaml.dump(
            data, Dumper=self._LiteralDumper, sort_keys=False, allow_unicode=True
        )


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

    update_date: date
    description: str
    link: str

    def to_list_string(self) -> str:
        return f"{self.link}"
    
    def to_prompt_string(self) -> str:
        return f"{self.link} | description: {self.description}"

class RunbookCatalog(BaseModel):
    catalog: List[Union[RunbookCatalogEntry, "RobustaRunbookInstruction"]]  # type: ignore

    def list_available_runbooks(self) -> list[str]:
        return [entry.to_list_string() for entry in self.catalog]

    def split_by_type(
        self,
    ) -> Tuple[List[RunbookCatalogEntry], List[RobustaRunbookInstruction]]:
        md: List[RunbookCatalogEntry] = []
        robusta: List[RobustaRunbookInstruction] = []  #
        for e in self.catalog:
            if isinstance(e, RunbookCatalogEntry):
                md.append(e)
            elif isinstance(e, RobustaRunbookInstruction):
                robusta.append(e)
        return md, robusta

    def to_prompt_string(self) -> str:
        md, robusta = self.split_by_type()
        parts: List[str] = [""]
        if md:
            parts.append("Here are MD runbooks:")
            parts.extend(f"* {e.to_prompt_string()}" for e in md)
        if robusta:
            parts.append("Here are Robusta runbooks:")
            parts.extend(f"* {e.to_prompt_string()}" for e in robusta)
        return "\n".join(parts)


def load_runbook_catalog(
    dal: Optional["SupabaseDal"] = None,
) -> Optional[RunbookCatalog]:  # type: ignore
    dir_path = os.path.dirname(os.path.realpath(__file__))

    catalogPath = os.path.join(dir_path, CATALOG_FILE)
    if not os.path.isfile(catalogPath):
        return None
    try:
        with open(catalogPath) as file:
            catalog_dict = json.load(file)
            catalog = RunbookCatalog(**catalog_dict)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {catalogPath}: {e}")
        return None
    except Exception as e:
        logging.error(
            f"Unexpected error while loading runbook catalog from {catalogPath}: {e}"
        )
        return None

    # Append additional runbooks from SupabaseDal if provided
    if dal and dal.enabled:
        try:
            supabase_entries = dal.get_runbook_catalog()
            if supabase_entries:
                catalog.catalog.extend(supabase_entries)
        except Exception as e:
            logging.error(f"Error loading runbooks from Supabase: {e}")

    return catalog


def get_runbook_by_path(
    runbook_relative_path: str, search_paths: List[str]
) -> Optional[str]:
    """
    Find a runbook by searching through provided paths.

    Args:
        runbook_relative_path: The relative path to the runbook
        search_paths: Optional list of directories to search. If None, uses default runbook folder.

    Returns:
        Full path to the runbook if found, None otherwise
    """
    # Validate runbook_relative_path is not empty
    if not runbook_relative_path or not runbook_relative_path.strip():
        return None

    for search_path in search_paths:
        runbook_path = os.path.join(search_path, runbook_relative_path)
        # Ensure it's a file, not a directory
        if os.path.isfile(runbook_path):
            return runbook_path

    return None
