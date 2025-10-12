from typing import Optional, List
from pydantic import BaseModel
import yaml


class RobustaRunbookInstruction(BaseModel):
    id: str
    symptom: str
    title: str
    instruction: Optional[str] = None

    class _LiteralDumper(yaml.SafeDumper):
        pass

    @staticmethod
    def _repr_str(dumper, s: str):
        s = s.replace("\\n", "\n")
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", s, style="|" if "\n" in s else None
        )

    # register representer (PyYAML API)
    _LiteralDumper.add_representer(str, _repr_str)  # type: ignore

    def to_list_string(self) -> str:
        return f"robusta runbook id='{self.id}'"

    def to_string(self) -> str:
        return f"robusta runbook id='{self.id}' | title='{self.title}' | symptom='{self.symptom}'"

    def pretty(self) -> str:
        try:
            data = self.model_dump(exclude_none=True)  # pydantic v2
        except AttributeError:
            data = self.dict(exclude_none=True)  # pydantic v1
        return yaml.dump(
            data, Dumper=self._LiteralDumper, sort_keys=False, allow_unicode=True
        )


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
