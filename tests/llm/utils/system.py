import socket
import platform
import os
import pwd
from datetime import datetime
from typing import Dict
from pathlib import Path


def get_active_branch_name():

    head_dir = Path(".") / ".git" / "HEAD"
    with head_dir.open("r") as f:
        content = f.read().splitlines()

        for line in content:
            if line[0:4] == "ref:":
                return line.partition("refs/heads/")[2]

    return "Unknown"

def get_machine_state_tags() -> Dict[str, str]:
    return {
        "username": pwd.getpwuid(os.getuid()).pw_name,
        "branch": get_active_branch_name(),
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
    }

def readable_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")
