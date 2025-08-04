from rich.console import Console
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from holmes.plugins.prompts import load_and_render_prompt
from holmes.plugins.runbooks import RunbookCatalog


def append_file_to_user_prompt(user_prompt: str, file_path: Path) -> str:
    with file_path.open("r") as f:
        user_prompt += f"\n\n<attached-file path='{file_path.absolute()}'>\n{f.read()}\n</attached-file>"

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
    initial_user_prompt: str,
    file_paths: Optional[List[Path]],
    tool_executor: Any,  # ToolExecutor type
    runbooks: Union[RunbookCatalog, Dict, None] = None,
    system_prompt_additions: Optional[str] = None,
) -> List[Dict]:
    """Build the initial messages for the AI call.

    Args:
        console: Rich console for output
        initial_user_prompt: The user's prompt
        file_paths: Optional list of files to include
        tool_executor: The tool executor with available toolsets
        runbooks: Optional runbook catalog
        system_prompt_additions: Optional additional system prompt content
    """
    # Load and render system prompt internally
    system_prompt_template = "builtin://generic_ask.jinja2"
    template_context = {
        "toolsets": tool_executor.toolsets,
        "runbooks": runbooks or {},
        "system_prompt_additions": system_prompt_additions or "",
    }
    system_prompt_rendered = load_and_render_prompt(
        system_prompt_template, template_context
    )

    # Append files to user prompt
    user_prompt_with_files = append_all_files_to_user_prompt(
        console, initial_user_prompt, file_paths
    )

    messages = [
        {"role": "system", "content": system_prompt_rendered},
        {"role": "user", "content": user_prompt_with_files},
    ]

    return messages
