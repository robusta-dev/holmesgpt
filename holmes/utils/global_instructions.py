from typing import List, Optional

from pydantic import BaseModel


class RobustaRunbookInstruction(BaseModel):
    id: str  # uuid
    symptom: str
    title: str
    instruction: Optional[str] = None

    def to_list_string(self) -> str:
        return f"robusta runbook id='{self.id}'"

    def to_string(self) -> str:
        """
        Print without instructions
        """
        return f"robusta runbook id='{self.id}' | title='{self.title} | symptom='{self.symptom}'"

    def pretty(self) -> str:
        try:
            return self.model_dump_json(indent=2, exclude_none=True)
        except AttributeError:
            return self.json(indent=2, exclude_none=True)


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
