from pathlib import Path


def append_file_to_user_prompt(user_prompt: str, file_path: Path) -> str:
    f = file_path.open("r")
    user_prompt += f"\n\nAttached file '{file_path.absolute()}':\n{f.read()}"

    return user_prompt
