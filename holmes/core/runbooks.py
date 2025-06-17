import logging
import os
from typing import List, Optional, Tuple

from holmes.core.issue import Issue
from holmes.core.llm import LLM
from holmes.plugins.runbooks import Runbook, get_runbook_folder, load_catalog


# TODO: our default prompt has a lot of kubernetes specific stuff - see if we can get that into the runbook
class RunbookManager:
    def __init__(self, runbooks: List[Runbook]):
        self.runbooks = runbooks

    def get_instructions_for_issue(self, issue: Issue) -> List[str]:
        instructions = []
        for runbook in self.runbooks:
            if runbook.match.issue_id and not runbook.match.issue_id.match(issue.id):
                continue
            if runbook.match.issue_name and not runbook.match.issue_name.match(
                issue.name
            ):
                continue
            if runbook.match.source and not runbook.match.source.match(
                issue.source_type
            ):
                continue
            instructions.append(runbook.instructions)

        return instructions


class RunbookCatalogManager:
    def __init__(self, llm: LLM, runbooks: Optional[List[str]] = None):
        """
        Initialize the RunbookCatalogManager with a list of runbooks and an LLM instance.
        :param llm: An instance of LLM to use for generating responses.
        :param runbooks: A list of custom runbooks. The custom runbooks will be returned without using the LLM.
        """

        self.runbooks = runbooks
        self.ai = llm
        self.catalog = load_catalog()

    def get_runbook_by_question(
        self, question: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the runbook content from the catalog based on the user question by LLM.
        If the runbook is not found or is empty, return None.
        """

        # TODO(mainred): currently we simply combine all runbooks into a single string and return it,
        # but we can consider selecting a specific runbook based on the question.
        if self.runbooks:
            combined_runbooks = ""
            for runbook_str in self.runbooks:
                combined_runbooks += f"* {runbook_str}\n"
            logging.debug("Custom runbooks are returned.")
            return combined_runbooks, None

        if not self.catalog:
            logging.debug("Runbook catalog is not loaded.")
            return None, None

        messages = [
            {
                "role": "system",
                "content": f"""
You are an assistant helping the user get the correct runbook to investigate the user question.
You are provided with a catalog of available runbooks with each entry including description and link, and you should return the link field when the description matches the user question.
When no runbook matches the user question, you should return empty string.
Here is the catalog of available runbooks:
{self.catalog.model_dump_json()}.
                """,
            },
            {"role": "user", "content": f"{question}"},
        ]
        response = self.ai.completion(messages, temperature=0)
        # when no runbook matches the user question, llm returns ""
        runbookAbsLink = response.choices[0].message.content.strip(' "')  # type: ignore
        if len(runbookAbsLink) == 0:
            logging.debug("No runbook found for the question.")
            return None, None
        else:
            logging.debug(f"Runbook link from LLM: {runbookAbsLink}")
        runbook_folder = get_runbook_folder()

        runbookPath = os.path.join(runbook_folder, runbookAbsLink)
        try:
            with open(runbookPath, "r") as file:
                content = file.read()
                if len(content.strip()) == 0:
                    print(f"Warning: The runbook '{runbookPath}' is empty.")
                    return None, runbookAbsLink
                # If the file is found and not empty, return its content
                return content, runbookAbsLink
        except FileNotFoundError:
            print(f"Error: The file '{runbookPath}' was not found.")
            return None, None
        except Exception as e:
            logging.error(f"An error occurred while reading the file: {e}")
            return None, None
