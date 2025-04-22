import base64
import logging
import requests
import os
from typing import Any, Optional, Dict, List
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

    def _sanitize_error(self, error_msg: str) -> str:
        """Sanitize error messages by removing sensitive information."""
        if not self.git_credentials:
            return error_msg
        return error_msg.replace(self.git_credentials, "[REDACTED]")

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

    def list_open_prs(self) -> List[Dict[str, Any]]:
        """Helper method to list all open PRs in the repository."""
        headers = {"Authorization": f"token {self.git_credentials}"}
        url = f"https://api.github.com/repos/{self.git_repo}/pulls?state=open"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise Exception(self._sanitize_error(f"Error listing PRs: {resp.text}"))
        return resp.json()

    def get_branch_ref(self, branch_name: str) -> Optional[str]:
        """Get the SHA of a branch reference."""
        headers = {"Authorization": f"token {self.git_credentials}"}
        url = (
            f"https://api.github.com/repos/{self.git_repo}/git/refs/heads/{branch_name}"
        )
        resp = requests.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise Exception(
                self._sanitize_error(f"Error getting branch reference: {resp.text}")
            )
        return resp.json()["object"]["sha"]

    def create_branch(self, branch_name: str, base_sha: str) -> None:
        """Create a new branch from a base SHA."""
        headers = {"Authorization": f"token {self.git_credentials}"}
        url = f"https://api.github.com/repos/{self.git_repo}/git/refs"
        resp = requests.post(
            url,
            headers=headers,
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha,
            },
        )
        if resp.status_code not in (200, 201):
            raise Exception(self._sanitize_error(f"Error creating branch: {resp.text}"))

    def get_file_content(self, filepath: str, branch: str) -> tuple[str, str]:
        """Get file content and SHA from a specific branch."""
        headers = {"Authorization": f"token {self.git_credentials}"}
        url = f"https://api.github.com/repos/{self.git_repo}/contents/{filepath}?ref={branch}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 404:
            raise Exception(f"File not found: {filepath}")
        if resp.status_code != 200:
            raise Exception(self._sanitize_error(f"Error fetching file: {resp.text}"))
        file_json = resp.json()
        return file_json["sha"], base64.b64decode(file_json["content"]).decode()

    def update_file(
        self, filepath: str, branch: str, content: str, sha: str, message: str
    ) -> None:
        """Update a file in a specific branch."""
        headers = {"Authorization": f"token {self.git_credentials}"}
        url = f"https://api.github.com/repos/{self.git_repo}/contents/{filepath}"
        encoded_content = base64.b64encode(content.encode()).decode()
        resp = requests.put(
            url,
            headers=headers,
            json={
                "message": message,
                "content": encoded_content,
                "branch": branch,
                "sha": sha,
            },
        )
        if resp.status_code not in (200, 201):
            raise Exception(self._sanitize_error(f"Error updating file: {resp.text}"))

    def create_pr(self, title: str, head: str, base: str, body: str) -> str:
        """Create a new pull request."""
        headers = {"Authorization": f"token {self.git_credentials}"}
        url = f"https://api.github.com/repos/{self.git_repo}/pulls"
        resp = requests.post(
            url,
            headers=headers,
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
        )
        if resp.status_code not in (200, 201):
            raise Exception(self._sanitize_error(f"Error creating PR: {resp.text}"))
        return resp.json()["html_url"]

    def get_pr_details(self, pr_number: int) -> Dict[str, Any]:
        """Get details of a specific PR."""
        headers = {"Authorization": f"token {self.git_credentials}"}
        url = f"https://api.github.com/repos/{self.git_repo}/pulls/{pr_number}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise Exception(
                self._sanitize_error(f"Error getting PR details: {resp.text}")
            )
        return resp.json()

    def get_pr_branch(self, pr_number: int) -> str:
        """Get the branch name for a specific PR."""
        pr_details = self.get_pr_details(pr_number)
        return pr_details["head"]["ref"]

    def add_commit_to_pr(
        self, pr_number: int, filepath: str, content: str, message: str
    ) -> None:
        """Add a commit to an existing PR's branch."""
        branch = self.get_pr_branch(pr_number)
        try:
            # Get current file content and SHA
            sha, _ = self.get_file_content(filepath, branch)
        except Exception:
            # File might not exist yet, that's okay
            sha = None

        # Update file
        headers = {"Authorization": f"token {self.git_credentials}"}
        url = f"https://api.github.com/repos/{self.git_repo}/contents/{filepath}"
        encoded_content = base64.b64encode(content.encode()).decode()
        data = {
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            data["sha"] = sha

        resp = requests.put(url, headers=headers, json=data)
        if resp.status_code not in (200, 201):
            raise Exception(
                self._sanitize_error(f"Error adding commit to PR: {resp.text}")
            )


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
            return self.toolset._sanitize_error(f"Error fetching file: {resp.text}")
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
            return self.toolset._sanitize_error(f"Error listing files: {resp.text}")
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
        try:
            prs = self.toolset.list_open_prs()
            return "\n".join(
                f"{pr['number']}: {pr['title']} - {pr['html_url']}" for pr in prs
            )
        except Exception as e:
            return self.toolset._sanitize_error(str(e))

    def get_parameterized_one_liner(self, params) -> str:
        return "Listing PR's"


class GitExecuteChanges(Tool):
    toolset: GitToolset

    def __init__(self, toolset: GitToolset):
        super().__init__(
            name="git_execute_changes",
            description="Make changes to a GitHub file and optionally open a PR or add to existing PR",
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
                    description="PR title or PR number to add commit to",
                    type="string",
                    required=True,
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
        try:
            line = params["line"]
            filename = params["filename"]
            command = params["command"]
            code = params.get("code", "")
            open_pr = params["open_pr"]
            commit_pr = params["commit_pr"]
            dry_run = params["dry_run"]
            commit_message = params["commit_message"]
            branch = self.toolset.git_branch

            # Validate inputs
            if not commit_message.strip():
                return "Commit message cannot be empty"
            if not filename.strip():
                return "Filename cannot be empty"
            if line < 1:
                return "Line number must be positive"

            # Check if commit_pr is a PR number (starts with #)
            if commit_pr.startswith("#"):
                try:
                    pr_number = int(commit_pr[1:])
                    # Get current file content from PR branch
                    branch = self.toolset.get_pr_branch(pr_number)
                    sha, content = self.toolset.get_file_content(filename, branch)
                    content_lines = content.splitlines()

                    # Update content
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
                        return f"DRY RUN: Updated content for PR #{pr_number}:\n\n{updated_content}"

                    # Add commit to PR
                    self.toolset.add_commit_to_pr(
                        pr_number, filename, updated_content, commit_message
                    )
                    return f"Added commit to PR #{pr_number} successfully"

                except ValueError:
                    return f"Invalid PR number format: {commit_pr}"
                except Exception as e:
                    return self.toolset._sanitize_error(
                        f"Error adding commit to PR: {str(e)}"
                    )

            # Original PR creation logic
            pr_name = commit_pr.replace(" ", "_").replace("'", "")
            branch_name = f"feature/{pr_name}"

            if not commit_pr.strip():
                return "PR title cannot be empty"

            # Check if branch already exists
            if self.toolset.get_branch_ref(branch_name) is not None:
                return f"Branch {branch_name} already exists. Please use a different PR title or manually delete the existing branch."

            # Check if PR with same title exists
            if open_pr:
                try:
                    existing_prs = self.toolset.list_open_prs()
                    for pr in existing_prs:
                        if pr["title"].lower() == commit_pr.lower():
                            return f"PR with title '{commit_pr}' already exists at {pr['html_url']}"
                except Exception as e:
                    return self.toolset._sanitize_error(
                        f"Error checking existing PRs: {str(e)}"
                    )

            # Get base branch SHA
            try:
                base_sha = self.toolset.get_branch_ref(branch)
                if base_sha is None:
                    return f"Base branch {branch} not found"
            except Exception as e:
                return self.toolset._sanitize_error(
                    f"Error getting base branch reference: {str(e)}"
                )

            # Get current file content
            try:
                sha, content = self.toolset.get_file_content(filename, branch)
                content_lines = content.splitlines()
            except Exception as e:
                return self.toolset._sanitize_error(
                    f"Error getting file content: {str(e)}"
                )

            # Validate line number
            if line > len(content_lines) + 1:
                return f"Line number {line} is out of range. File has {len(content_lines)} lines."

            # Update content
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

            # Create new branch
            try:
                self.toolset.create_branch(branch_name, base_sha)
            except Exception as e:
                return self.toolset._sanitize_error(f"Error creating branch: {str(e)}")

            # Update file
            try:
                self.toolset.update_file(
                    filename, branch_name, updated_content, sha, commit_message
                )
            except Exception as e:
                return self.toolset._sanitize_error(
                    f"Error updating file: {str(e)}. The branch {branch_name} was created but the commit failed. Please manually delete the branch if needed."
                )

            # Create PR if requested
            if open_pr:
                try:
                    pr_url = self.toolset.create_pr(
                        commit_pr, branch_name, branch, commit_message
                    )
                    return f"PR opened successfully: {pr_url}"
                except Exception as e:
                    return self.toolset._sanitize_error(
                        f"Error creating PR: {str(e)}. The branch {branch_name} was created and committed successfully, but PR creation failed. Please manually create a PR from this branch if needed."
                    )

            return "Change committed successfully, no PR opened."

        except requests.exceptions.RequestException as e:
            return self.toolset._sanitize_error(f"Network error: {str(e)}")
        except Exception as e:
            return self.toolset._sanitize_error(f"Unexpected error: {str(e)}")

    def get_parameterized_one_liner(self, params) -> str:
        return (
            f"git execute_changes(line={params['line']}, filename='{params['filename']}', "
            f"command='{params['command']}', code='{params.get('code', '')}', "
            f"open_pr={params['open_pr']}, commit_pr='{params['commit_pr']}', "
            f"dry_run={params['dry_run']}, commit_message='{params['commit_message']}')"
        )
