import base64
import logging
import requests
import os
from typing import Any, Optional, Dict
from pydantic import BaseModel

from holmes.core.tools import (
    Toolset,
    Tool,
    ToolParameter,
    ToolsetTag,
    CallablePrerequisite,
)


class GitHubConfig(BaseModel):
    git_repo: str
    git_credentials: str
    git_branch: str = "main"


class GitToolset(Toolset):
    git_repo: Optional[str] = None
    git_credentials: Optional[str] = None
    git_branch: Optional[str] = None

    def __init__(self):
        super().__init__(
            name="git",
            description="Runs git commands to read repos and create PRs",
            docs_url="https://docs.github.com/en/rest",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[
                GitReadFileWithLineNumbers(self),
                GitListFiles(self),
                GitListOpenPRs(self),
                GitExecuteChanges(self),
            ],
            tags=[ToolsetTag.CORE],
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        try:
            self.git_repo = os.getenv("GIT_REPO") or config.get("git_repo")
            self.git_credentials = os.getenv("GIT_CREDENTIALS") or config.get(
                "git_credentials"
            )
            self.git_branch = os.getenv("GIT_BRANCH") or config.get(
                "git_branch", "main"
            )

            if not all([self.git_repo, self.git_credentials, self.git_branch]):
                logging.error("Missing one or more required Git configuration values.")
                return False, ""
            return True, ""
        except Exception:
            logging.exception("GitHub prerequisites failed.")
            return False, ""

    def get_example_config(self) -> Dict[str, Any]:
        return {}


class GitReadFileWithLineNumbers(Tool):
    toolset: GitToolset

    def __init__(self, toolset: GitToolset):
        super().__init__(
            name="git_read_file_with_line_numbers",
            description="Reads a file from the Git repo and prints each line with line numbers",
            parameters={
                "filepath": ToolParameter(
                    description="The path of the file in the repository to read.",
                    type="string",
                    required=True,
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        filepath = params["filepath"]
        headers = {"Authorization": f"token {self.toolset.git_credentials}"}
        url = (
            f"https://api.github.com/repos/{self.toolset.git_repo}/contents/{filepath}"
        )
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return f"Error fetching file: {resp.text}"
        content = base64.b64decode(resp.json()["content"]).decode().splitlines()
        return "\n".join(f"{i+1}: {line}" for i, line in enumerate(content))

    def get_parameterized_one_liner(self, params) -> str:
        return "Reading git files"


class GitListFiles(Tool):
    toolset: GitToolset

    def __init__(self, toolset: GitToolset):
        super().__init__(
            name="git_list_files",
            description="Lists all files and directories in the remote Git repository.",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        headers = {"Authorization": f"token {self.toolset.git_credentials}"}
        url = f"https://api.github.com/repos/{self.toolset.git_repo}/git/trees/{self.toolset.git_branch}?recursive=1"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return f"Error listing files: {resp.text}"
        return "\n".join(entry["path"] for entry in resp.json()["tree"])

    def get_parameterized_one_liner(self, params) -> str:
        return "listing git files"


class GitListOpenPRs(Tool):
    toolset: GitToolset

    def __init__(self, toolset: GitToolset):
        super().__init__(
            name="git_list_open_prs",
            description="Lists all open pull requests (PRs) in the remote Git repository.",
            parameters={},
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        headers = {"Authorization": f"token {self.toolset.git_credentials}"}
        url = f"https://api.github.com/repos/{self.toolset.git_repo}/pulls?state=open"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return f"Error listing PRs: {resp.text}"
        prs = resp.json()
        return "\n".join(
            f"{pr['number']}: {pr['title']} - {pr['html_url']}" for pr in prs
        )

    def get_parameterized_one_liner(self, params) -> str:
        return "Listing PR's"


class GitExecuteChanges(Tool):
    toolset: GitToolset

    def __init__(self, toolset: GitToolset):
        super().__init__(
            name="git_execute_changes",
            description="Make changes to a GitHub file and optionally open a PR",
            parameters={
                "line": ToolParameter(
                    description="Line number to change", type="integer", required=True
                ),
                "filename": ToolParameter(
                    description="Filename (relative path)", type="string", required=True
                ),
                "command": ToolParameter(
                    description="insert/update/remove", type="string", required=True
                ),
                "code": ToolParameter(
                    description="Code to insert or update",
                    type="string",
                    required=False,
                ),
                "open_pr": ToolParameter(
                    description="Whether to open PR", type="boolean", required=True
                ),
                "commit_pr": ToolParameter(
                    description="PR title", type="string", required=True
                ),
                "dry_run": ToolParameter(
                    description="Dry-run mode", type="boolean", required=True
                ),
                "commit_message": ToolParameter(
                    description="Commit message", type="string", required=True
                ),
            },
            toolset=toolset,
        )

    def _invoke(self, params: Any) -> str:
        line = params["line"]
        filename = params["filename"]
        command = params["command"]
        code = params.get("code", "")
        open_pr = params["open_pr"]
        commit_pr = params["commit_pr"]
        dry_run = params["dry_run"]
        commit_message = params["commit_message"]
        token = self.toolset.git_credentials
        repo = self.toolset.git_repo
        branch = self.toolset.git_branch
        pr_name = commit_pr.replace(" ", "_").replace("'", "")
        branch_name = f"feature/{pr_name}"

        # Step 1: Fetch file content
        headers = {"Authorization": f"token {token}"}
        file_url = f"https://api.github.com/repos/{repo}/contents/{filename}"
        file_resp = requests.get(file_url, headers=headers)
        if file_resp.status_code != 200:
            return f"Failed to fetch file content: {file_resp.text}"

        file_json = file_resp.json()
        sha = file_json["sha"]
        content_lines = base64.b64decode(file_json["content"]).decode().splitlines()

        # Step 2: Update content
        if command == "insert":
            content_lines.insert(line - 1, code)
        elif command == "update":
            indent = len(content_lines[line - 1]) - len(
                content_lines[line - 1].lstrip()
            )
            content_lines[line - 1] = " " * indent + code
        elif command == "remove":
            del content_lines[line - 1]
        else:
            return f"Invalid command: {command}"

        updated_content = "\n".join(content_lines) + "\n"

        if dry_run:
            return f"DRY RUN: Updated content:\n\n{updated_content}"

        # Step 3: Create new branch
        ref_url = f"https://api.github.com/repos/{repo}/git/refs/heads/{branch}"
        ref_resp = requests.get(ref_url, headers=headers)
        sha_base = ref_resp.json()["object"]["sha"]

        create_branch_url = f"https://api.github.com/repos/{repo}/git/refs"
        requests.post(
            create_branch_url,
            headers=headers,
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": sha_base,
            },
        )

        # Step 4: Commit updated content
        update_file_url = f"https://api.github.com/repos/{repo}/contents/{filename}"
        encoded_content = base64.b64encode(updated_content.encode()).decode()
        commit_resp = requests.put(
            update_file_url,
            headers=headers,
            json={
                "message": commit_message,
                "content": encoded_content,
                "branch": branch_name,
                "sha": sha,
            },
        )

        if commit_resp.status_code not in (200, 201):
            return f"Failed to commit file: {commit_resp.text}"

        # Step 5: Open PR
        if open_pr:
            pr_url = f"https://api.github.com/repos/{repo}/pulls"
            pr_resp = requests.post(
                pr_url,
                headers=headers,
                json={
                    "title": commit_pr,
                    "body": commit_message,
                    "head": branch_name,
                    "base": branch,
                },
            )
            if pr_resp.status_code not in (200, 201):
                return f"Failed to open PR: {pr_resp.text}"
            return f"PR opened successfully: {pr_resp.json().get('html_url')}"

        return "Change committed successfully, no PR opened."

    def get_parameterized_one_liner(self, params) -> str:
        return (
            f"git execute_changes(line={params['line']}, filename='{params['filename']}', "
            f"command='{params['command']}', code='{params.get('code', '')}', "
            f"open_pr={params['open_pr']}, commit_pr='{params['commit_pr']}', "
            f"dry_run={params['dry_run']}, commit_message='{params['commit_message']}')"
        )
