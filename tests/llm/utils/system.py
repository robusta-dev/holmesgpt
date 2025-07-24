import socket
import platform
import os
import pwd
from datetime import datetime
from typing import Dict
from pathlib import Path


def get_active_branch_name():
    try:
        # First check if .git is a file (worktree case)
        git_path = Path(".git")
        if git_path.is_file():
            # Read the worktree git directory path
            with git_path.open("r") as f:
                content = f.read().strip()
                if content.startswith("gitdir:"):
                    worktree_git_dir = Path(content.split("gitdir:", 1)[1].strip())
                    head_file = worktree_git_dir / "HEAD"
                else:
                    return "Unknown"
        else:
            # Regular .git directory
            head_file = git_path / "HEAD"

        with head_file.open("r") as f:
            content = f.read().splitlines()
            for line in content:
                if line[0:4] == "ref:":
                    return line.partition("refs/heads/")[2]
    except Exception:
        pass

    return "Unknown"


def get_machine_state_tags() -> Dict[str, str]:
    return {
        "username": pwd.getpwuid(os.getuid()).pw_name,
        "branch": get_active_branch_name(),
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
    }


session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


def readable_timestamp():
    return session_timestamp
