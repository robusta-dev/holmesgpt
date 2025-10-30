from typing import Optional, List, TYPE_CHECKING, Dict
from pydantic import BaseModel
from holmes.plugins.prompts import load_and_render_prompt
from holmes.plugins.runbooks import RunbookCatalog

if TYPE_CHECKING:
    from holmes.core.resource_instruction import ResourceInstructions


class Instructions(BaseModel):
    instructions: List[str] = []


def _format_instructions_block(
    items: List[str], header: str = "My instructions to check:"
) -> str:
    lines = [f"* {s}" for s in items if isinstance(s, str) and s.strip()]
    if not lines:
        return ""
    bullets = "\n".join(lines) + "\n"
    return f"{header}\n{bullets}"


def _format_resource_instructions(
    resource_instructions: Optional["ResourceInstructions"],
) -> List[str]:  # type: ignore
    items = []
    if resource_instructions is not None:
        if getattr(resource_instructions, "instructions", None):
            items.extend(resource_instructions.instructions)
        if getattr(resource_instructions, "documents", None):
            for document in resource_instructions.documents:
                items.append(f"fetch information from this URL: {document.url}")
    return items


def generate_runbooks_args(
    runbook_catalog: Optional[RunbookCatalog],
    global_instructions: Optional[Instructions] = None,
    issue_instructions: Optional[List[str]] = None,
    resource_instructions: Optional["ResourceInstructions"] = None,  # type: ignore
) -> Dict[str, str]:
    catalog_str = runbook_catalog.to_prompt_string() if runbook_catalog else ""

    combined_instructions = []
    if issue_instructions:
        combined_instructions.extend(issue_instructions)
    combined_instructions.extend(_format_resource_instructions(resource_instructions))
    issue_block = (
        _format_instructions_block(combined_instructions)
        if combined_instructions
        else ""
    )

    gi_list = getattr(global_instructions, "instructions", None) or []
    global_block = (
        _format_instructions_block(
            [s for s in gi_list if isinstance(s, str)], header=""
        )
        if gi_list
        else ""
    )

    return {
        "runbook_catalog": catalog_str,
        "custom_instructions": issue_block,
        "global_instructions": global_block,
    }


def _has_content(value: Optional[str]) -> bool:
    """
    Check if the value is a non-empty string and not None.
    """
    return bool(value and isinstance(value, str) and value.strip())


def _should_enable_runbooks(context: Dict[str, str]) -> bool:
    return any(
        (
            _has_content(context.get("runbook_catalog")),
            _has_content(context.get("custom_instructions")),
            _has_content(context.get("global_instructions")),
        )
    )


def generate_user_prompt(
    user_prompt: str,
    context: Dict[str, str],
) -> str:
    runbooks_enabled = _should_enable_runbooks(context)

    return load_and_render_prompt(
        "builtin://base_user_prompt.jinja2",
        context={
            "user_prompt": user_prompt,
            "runbooks_enabled": runbooks_enabled,
            **context,
        },
    )
