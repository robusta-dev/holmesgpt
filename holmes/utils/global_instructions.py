from typing import List, Optional

from pydantic import BaseModel


class Instructions(BaseModel):
    instructions: List[str] = []


def add_global_instructions_to_user_prompt(
    user_prompt: str, global_instructions: Optional[Instructions]
) -> str:
    if (
        global_instructions
        and global_instructions.instructions
        and len(global_instructions.instructions[0]) > 0
    ):
        instructions = "\n\n".join(global_instructions.instructions)
        user_prompt += f"\n\nGlobal Instructions (use if relevant): {instructions}\n"
    return user_prompt
