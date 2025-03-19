from typing import Optional
from holmes.core.tool_calling_llm import Instructions


def add_global_instructions_to_user_prompt(
    user_prompt: str, global_instructions: Optional[Instructions]
) -> str:
    if (
        global_instructions
        and global_instructions.instructions
        and len(global_instructions.instructions[0]) > 0
    ):
        instructions = "\n\n".join(global_instructions.instructions)
        user_prompt += f"\n\nGlobal Instructions (use only if relevant): {instructions}\n"
    return user_prompt
