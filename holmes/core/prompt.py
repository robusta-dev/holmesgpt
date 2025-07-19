from rich.console import Console
from typing import Optional, List, Dict
from pathlib import Path


def append_file_to_user_prompt(user_prompt: str, file_path: Path) -> str:
    with file_path.open("r") as f:
        user_prompt += f"\n\n<attached-file path='{file_path.absolute()}>'\n{f.read()}\n</attached-file>"

    return user_prompt


def append_all_files_to_user_prompt(
    console: Console, user_prompt: str, file_paths: Optional[List[Path]]
) -> str:
    if not file_paths:
        return user_prompt

    for file_path in file_paths:
        console.print(f"[bold yellow]Adding file {file_path} to context[/bold yellow]")
        user_prompt = append_file_to_user_prompt(user_prompt, file_path)

    return user_prompt


def build_initial_ask_messages(
    console: Console,
    system_prompt_rendered: str,
    initial_user_prompt: str,
    file_paths: Optional[List[Path]],
) -> List[Dict]:
    """Build the initial messages for the AI call."""
    user_prompt_with_files = append_all_files_to_user_prompt(
        console, initial_user_prompt, file_paths
    )

    messages = [
        {"role": "system", "content": system_prompt_rendered},
        {"role": "user", "content": user_prompt_with_files},
    ]

    return messages
