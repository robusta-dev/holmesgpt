"""Find command implementation for interactive mode."""

import re
from typing import Dict, List, Optional, Union, Tuple

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import has_completions
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.shortcuts.prompt import CompleteStyle
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator, ValidationError
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from holmes.cli.utils import show_scrollable_modal
from holmes.core.tool_calling_llm import ToolCallingLLM
from holmes.core.tracing import DummySpan


# Color constants
AI_COLOR = "#00FFFF"  # cyan
ERROR_COLOR = "red"
STATUS_COLOR = "yellow"
TOOLS_COLOR = "magenta"


class ActionMenuCompleter(Completer):
    """Completer for action menu selections with arrow navigation"""

    def __init__(self, actions_list, add_back_option=True):
        self.actions = actions_list
        self.all_options = [(num, desc) for num, desc in actions_list]

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lower()

        # Always show all options, but style based on whether they match
        for num, desc in self.all_options:
            # Check if this option matches the filter
            matches = (
                not text
                or desc.lower().find(text) >= 0
                or num.startswith(text)
                or (num == "b" and "back".startswith(text))
            )

            # Truncate long descriptions
            display_text = desc[:70] + "..." if len(desc) > 70 else desc

            # Style non-matching items differently
            if not matches and text:
                # Dim style for non-matching items - append to base style
                style = "class:completion-menu.meta"
            else:
                # Normal style for matching items
                style = ""

            # Always yield all completions
            yield Completion(
                text=desc,  # Insert full description when selected
                start_position=-len(document.text),  # Replace all typed text
                display=display_text,  # What's shown in the menu
                style=style,  # Apply dimmed style to non-matches
            )


class ActionMenuValidator(Validator):
    """Validator for action menu selections"""

    def __init__(self, actions_list):
        self.valid_values = {}  # Map descriptions to numbers
        for num, desc in actions_list:
            self.valid_values[desc] = num
            self.valid_values[num] = num  # Also accept numbers directly

    def validate(self, document):
        text = document.text.strip()
        if text not in self.valid_values:
            raise ValidationError(
                message="Invalid selection. Please select from the menu."
            )


def _search_resources(
    find_args: str,
    ai: ToolCallingLLM,
    console: Console,
    messages: Optional[List[Dict]],
) -> Optional[tuple[str, List[Dict]]]:
    """
    Search for resources using LLM.
    Returns (resources_found, updated_messages) or None if no resources found.
    """
    search_prompt = f"""
The user wants to look up a resource: {find_args}

Please search across all available toolsets (Kubernetes, GCP, AWS, etc.) for resources matching this query.
Use tools like kubectl_find_resource, kubectl_get_by_kind_in_cluster, and any GCP/AWS search tools available.

After gathering results, format them EXACTLY like this:

🐳 Kubernetes
├─ [1] Pod: nginx-web-7d9f8b6c5-x2kt4 (namespace: default)
│      └─ Running on node-1, IP: 10.0.1.5
└─ [2] Service: nginx-service (namespace: default)
       └─ LoadBalancer: 34.102.136.180:80

☁️ GCP
└─ [3] GCE Instance: nginx-prod (zone: us-central1-a)
       └─ Running, External IP: 35.202.123.45

IMPORTANT:
- Use inline numbers [1], [2], etc. for each resource
- Continue numbering across providers (don't restart at 1)
- Only show providers that have results
- If no resources found at all, respond with ONLY: "No resources found matching '{find_args}'"
- DO NOT add any summary or extra text after the tree structure
- The response should ONLY contain the tree structure, nothing before or after it
"""

    # Build messages for the lookup
    lookup_messages: List[Dict] = messages.copy() if messages else []
    lookup_messages.append({"role": "user", "content": search_prompt})

    # Get search results from LLM
    console.print(
        f"[bold {AI_COLOR}]Entering find mode - searching for '{find_args}'...[/bold {AI_COLOR}]\n"
    )
    search_response = ai.call(lookup_messages, trace_span=DummySpan())

    # Store the search results
    resources_found = search_response.result or ""
    lookup_messages = search_response.messages or []

    # Check if no results found
    if resources_found.strip().startswith("No resources found"):
        console.print(resources_found)
        return None

    return resources_found, lookup_messages


def _create_menu_key_bindings(
    completer: ActionMenuCompleter, with_tab: bool = False
) -> KeyBindings:
    """
    Create key bindings for menu selection.

    Args:
        completer: The completer for the menu
        with_tab: Whether to include Tab/Ctrl+Space bindings for action menus
    """
    bindings = KeyBindings()

    if with_tab:

        @bindings.add("c-space")
        @bindings.add("tab")
        def handle_tab(event):
            """Show completions on Tab or Ctrl+Space"""
            b = event.app.current_buffer
            if b.complete_state:
                b.complete_next()
            else:
                b.start_completion(select_first=True)

    @bindings.add("escape")
    def handle_escape(event):
        """Override Escape to keep menu open"""
        b = event.app.current_buffer
        b.reset()
        b.start_completion(select_first=True)

    @bindings.add("backspace")
    def handle_backspace(event):
        """Smart backspace for selection"""
        b = event.app.current_buffer
        valid_descriptions = [desc for _, desc in completer.all_options]

        if b.text in valid_descriptions:
            b.text = ""
        elif b.text:
            b.delete_before_cursor()

        b.start_completion(select_first=True)

    @bindings.add(Keys.Any, filter=~has_completions)
    def handle_any_key(event):
        """Auto-show completions after any key press"""
        event.app.current_buffer.insert_text(event.data)
        event.app.current_buffer.start_completion(select_first=False)

    return bindings


def _prompt_for_selection(
    resource_list: List[tuple[str, str]],
    find_style: Style,
    console: Console,
) -> str:
    """
    Prompt user to select a resource from the list.
    Returns the selected resource number.
    """
    # Create completer and validator
    resource_completer = ActionMenuCompleter(resource_list, add_back_option=False)
    resource_validator = ActionMenuValidator(resource_list)

    # Create key bindings (without Tab for resource selection)
    resource_bindings = _create_menu_key_bindings(resource_completer, with_tab=False)

    # Create a temporary session with resource completion
    modal_session: PromptSession = PromptSession(
        completer=resource_completer,
        validator=resource_validator,
        validate_while_typing=False,
        complete_while_typing=True,
        history=InMemoryHistory(),
        complete_style=CompleteStyle.COLUMN,
        reserve_space_for_menu=min(10, len(resource_list) + 2),
        key_bindings=resource_bindings,
    )

    console.print(
        "[dim]Type to filter or use ↑↓ arrows, Enter to select (Ctrl-C to exit)[/dim]"
    )

    # Pre-run to show menu immediately
    def pre_run():
        app = modal_session.app
        if app:
            app.current_buffer.start_completion(select_first=True)

    # Prompt for selection
    selection = modal_session.prompt(
        [("class:prompt", "> ")], style=find_style, pre_run=pre_run
    )

    # Convert description back to number if needed
    if selection in resource_validator.valid_values:
        return resource_validator.valid_values[selection]
    return selection


def _fetch_resource_details(
    selection: str,
    lookup_messages: List[Dict],
    ai: ToolCallingLLM,
    console: Console,
) -> tuple:
    """
    Fetch detailed information about the selected resource.
    Returns (detail_response, updated_messages).
    """
    detail_prompt = f"""
The user selected option [{selection}] from the search results above.

Please:
1. Use appropriate tools to get detailed information about this specific resource
2. Present the key details in a clean, concise format
3. Do NOT include an "Available Actions" section in your response

IMPORTANT: Also include a section at the very end of your response in this exact format:
```actions
1|Show full details (kubectl describe)
2|Show YAML
3|Show logs
4|Show events
5|/run kubectl exec -it <actual-pod-name> -n <actual-namespace> -- sh
6|/run kubectl port-forward <actual-pod-name> -n <actual-namespace> 8080:80
7|/run kubectl logs <actual-pod-name> -n <actual-namespace> --tail=100
```

For GCP resources, include similar appropriate actions in the actions block.
"""

    lookup_messages.append({"role": "user", "content": detail_prompt})

    console.print(f"[bold {AI_COLOR}]Getting details...[/bold {AI_COLOR}]\n")
    detail_response = ai.call(lookup_messages, trace_span=DummySpan())

    return detail_response, lookup_messages


def _process_resource_details(
    detail_text: str, console: Console
) -> List[tuple[str, str]]:
    """
    Display resource details and extract available actions.
    Returns list of (number, description) tuples for actions.
    """
    # Remove the ```actions...``` block from display
    display_text = re.sub(r"```actions\n.*?```", "", detail_text, flags=re.DOTALL)
    # Also remove extra newlines that might be left
    display_text = re.sub(r"\n{3,}", "\n\n", display_text.strip())

    console.print(
        Panel(
            Markdown(display_text),
            padding=(1, 2),
            border_style=AI_COLOR,
            title="Resource Details",
            title_align="left",
        )
    )

    # Extract actions from the response
    actions_list = []
    actions_match = re.search(r"```actions\n(.*?)```", detail_text, re.DOTALL)
    if actions_match:
        actions_text = actions_match.group(1).strip()
        for line in actions_text.split("\n"):
            if "|" in line:
                num, desc = line.split("|", 1)
                actions_list.append((num.strip(), desc.strip()))
    return actions_list


def _handle_action_selection(
    actions_list: List[tuple[str, str]],
    selection: str,
    find_style: Style,
    console: Console,
) -> Optional[str]:
    """
    Handle action selection for a resource.
    Returns:
        - Selected action number if action was selected
        - None if user cancelled (Ctrl-C)
        - "continue" if user should stay in action loop
    """
    console.print()  # Blank line for spacing

    if not actions_list:
        # No actions available for this resource
        console.print(
            Panel(
                f"[bold {STATUS_COLOR}]No actions available[/bold {STATUS_COLOR}]\n\n"
                f"[dim]The selected resource ({selection}) doesn't have any available actions.\n"
                "This might be because:\n"
                "• The resource type doesn't support interactive actions\n"
                "• The resource is in a state where actions aren't applicable\n"
                "• Additional permissions may be required\n\n"
                "Press Ctrl-C to go back to the resource list.[/dim]",
                padding=(1, 2),
                border_style=STATUS_COLOR,
                title="No Actions",
                title_align="left",
            )
        )
        # Wait for Ctrl-C to go back
        try:
            temp_session: PromptSession = PromptSession(history=InMemoryHistory())
            temp_session.prompt(
                [("class:prompt", "Press Ctrl-C to go back: ")],
                style=find_style,
            )
        except KeyboardInterrupt:
            return None  # Go back to resource selection
        return "continue"  # If they somehow entered something, stay in the loop

    # Show action menu
    console.print(f"[bold {AI_COLOR}]Select action for {selection}:[/bold {AI_COLOR}]")

    # Create completer and validator
    action_completer = ActionMenuCompleter(actions_list)
    action_validator = ActionMenuValidator(actions_list)

    # Create key bindings (with Tab for action menus)
    action_bindings = _create_menu_key_bindings(action_completer, with_tab=True)

    # Create a temporary session with menu-style completion
    menu_session: PromptSession = PromptSession(
        completer=action_completer,
        validator=action_validator,
        validate_while_typing=False,
        complete_while_typing=True,
        history=InMemoryHistory(),
        complete_style=CompleteStyle.COLUMN,
        reserve_space_for_menu=min(10, len(actions_list) + 2),
        key_bindings=action_bindings,
    )

    # Show instruction and prompt
    console.print(
        "[dim]Type to filter or use ↑↓ arrows, Enter to select (Ctrl-C to go back)[/dim]"
    )

    # Define pre_run to auto-start completion
    def pre_run():
        app = menu_session.app
        if app:
            app.current_buffer.start_completion(select_first=True)

    try:
        action_selection = menu_session.prompt(
            [("class:prompt", "> ")],
            style=find_style,
            default="",
            pre_run=pre_run,
        )

        # Convert description back to number if needed
        if action_selection in action_validator.valid_values:
            return action_validator.valid_values[action_selection]
        return action_selection
    except KeyboardInterrupt:
        return None  # Go back to resource selection


def _execute_action(
    action_number: str,
    detail_result: str,
    lookup_messages: List[Dict],
    ai: ToolCallingLLM,
    console: Console,
) -> Optional[Union[str, Tuple[None, List[Dict]]]]:
    """
    Execute the selected action.
    Returns:
        - /run command string if action is a run command
        - (None, updated_messages) tuple if action was executed and displayed
        - None if invalid selection
    """
    if action_number is None or action_number == "continue":
        return None

    # Check if this is a /run command
    if "/run" in detail_result:
        # Let LLM extract and execute the action
        action_prompt = f"""
The user selected action [{action_number}] from the list above.

If this action is a /run command, please extract and return ONLY the /run command line.
If it's a describe/show action, execute it using the appropriate tool and show the output.

For /run commands, respond with ONLY the command like:
/run kubectl exec -it nginx-pod -- sh

For other actions:
1. First output a line starting with "EXECUTING: " that describes what you're doing (e.g., "EXECUTING: Showing pod YAML")
2. Then execute the tool and present the results

IMPORTANT: For "Show logs" actions, use fetch_pod_logs which defaults to 100 lines. This is usually sufficient. Only if the user asks for more logs or you need to see earlier logs, use a higher limit.
"""
        lookup_messages.append({"role": "user", "content": action_prompt})

        action_response = ai.call(lookup_messages, trace_span=DummySpan())
        action_result = action_response.result or ""

        # Check if response is a /run command
        if action_result.strip().startswith("/run"):
            # Return the command to be executed in main loop
            return action_result.strip()
        else:
            # Extract the action description from EXECUTING line if present
            modal_title = f"Action {action_number} Result"
            exec_match = re.search(
                r"^EXECUTING:\s*(.+?)(?:\n|$)",
                action_result,
                re.MULTILINE,
            )
            if exec_match:
                modal_title = exec_match.group(1)
                # Remove the EXECUTING line from the result
                action_result = re.sub(
                    r"^EXECUTING:.*\n",
                    "",
                    action_result,
                    flags=re.MULTILINE,
                )

            # Display the action result in a modal
            show_scrollable_modal(action_result, modal_title, console)

            # Return updated messages
            return (None, action_response.messages or [])
    else:
        console.print(f"[bold {ERROR_COLOR}]Invalid selection[/bold {ERROR_COLOR}]")
        return None


def handle_find_modal(
    find_args: str,
    ai: ToolCallingLLM,
    console: Console,
    messages: Optional[List[Dict]],
    session: PromptSession,
    style: Style,
) -> Optional[str]:
    """
    Handle /find as a modal interaction with its own loop.
    Returns a command to execute (like /run) or None.
    """
    # Phase 1: Search using LLM
    search_result = _search_resources(find_args, ai, console, messages)
    if search_result is None:
        return None

    resources_found, lookup_messages = search_result

    # Create style for find mode prompts
    find_style = Style.from_dict(
        {
            "prompt": AI_COLOR,  # Use AI_COLOR for find mode prompts
            "completion-menu": "bg:#1a1a1a #888888",  # Dark background, gray text
            "completion-menu.completion.current": "bg:#1a1a1a #ffffff",  # White text for selected
            "completion-menu.meta": "bg:#1a1a1a #666666",  # Darker gray for meta
            "completion-menu.meta.current": "bg:#1a1a1a #888888",  # Slightly brighter for selected meta
        }
    )

    # Phase 2: Interactive selection loop
    try:
        while True:
            # Display search results
            console.print(
                Panel(
                    resources_found,
                    padding=(1, 2),
                    border_style=AI_COLOR,
                    title="Search Results",
                    title_align="left",
                )
            )

            console.print()  # Add blank line for clarity

            # Parse resources from the LLM response
            resource_list = []
            for line in resources_found.split("\n"):
                # Look for lines with [number] pattern
                match = re.search(r"\[(\d+)\]\s+(.+)", line)
                if match:
                    num, desc = match.groups()
                    # Clean up the description
                    desc = desc.strip()
                    resource_list.append((num, desc))

            # Prompt for resource selection
            selection = _prompt_for_selection(resource_list, find_style, console)

            try:
                # Phase 3: Show resource details with actions
                detail_response, lookup_messages = _fetch_resource_details(
                    selection, lookup_messages, ai, console
                )

                # Process and display resource details
                actions_list = _process_resource_details(
                    detail_response.result or "", console
                )

                # Phase 4: Action selection loop
                while True:
                    # Handle action selection
                    action_result = _handle_action_selection(
                        actions_list, selection, find_style, console
                    )

                    if action_result is None:
                        # User cancelled or no actions available
                        break
                    elif action_result == "continue":
                        # Stay in action loop
                        continue

                    # Process the selected action
                    result = _execute_action(
                        action_result,
                        detail_response.result or "",
                        lookup_messages,
                        ai,
                        console,
                    )

                    if isinstance(result, str):
                        # Return /run command to be executed in main loop
                        return result
                    elif isinstance(result, tuple):
                        # Update messages and continue
                        _, lookup_messages = result

            except (ValueError, IndexError):
                console.print(
                    f"[bold {ERROR_COLOR}]Invalid selection[/bold {ERROR_COLOR}]"
                )
    except KeyboardInterrupt:
        console.print(f"\n[bold {AI_COLOR}]Exiting find mode.[/bold {AI_COLOR}]")
        return None
