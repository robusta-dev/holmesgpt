import logging
from typing import Dict, List
from threading import Lock
from uuid import uuid4

from holmes.core.tools import Task, TaskStatus


class TodoListManager:
    """
    Session-based storage manager for investigation TodoLists.
    Stores TodoLists per session and provides methods to get/update tasks.
    """

    def __init__(self):
        self._sessions: Dict[str, List[Task]] = {}
        self._lock = Lock()

    def get_session_tasks(self, session_id: str) -> List[Task]:
        """Get all tasks for a session. Returns empty list if session doesn't exist."""
        logging.info(f"########## get_session_tasks {session_id}")
        with self._lock:
            return self._sessions.get(session_id, []).copy()

    def update_session_tasks(self, session_id: str, tasks: List[Task]) -> None:
        """Update all tasks for a session."""
        with self._lock:
            self._sessions[session_id] = tasks.copy()

    def clear_session(self, session_id: str) -> None:
        """Clear all tasks for a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def get_session_count(self) -> int:
        """Get number of active sessions (for debugging/testing)."""
        with self._lock:
            return len(self._sessions)

    def format_tasks_for_prompt(self, session_id: str) -> str:
        """
        Format tasks for injection into system prompt.
        Returns empty string if no tasks exist.
        """
        tasks = self.get_session_tasks(session_id)

        if not tasks:
            return ""

        # Sort tasks by status (pending -> in_progress -> completed) then priority
        status_order = {"pending": 0, "in_progress": 1, "completed": 2}

        sorted_tasks = sorted(
            tasks,
            key=lambda t: (status_order.get(t.status.value, 3),),
        )

        lines = ["# CURRENT INVESTIGATION TASKS"]
        lines.append("")

        # Count tasks by status
        pending_count = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
        progress_count = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
        completed_count = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)

        lines.append(
            f"**Task Status**: {completed_count} completed, {progress_count} in progress, {pending_count} pending"
        )
        lines.append("")

        for task in sorted_tasks:
            # Use simple text indicators for prompt injection
            status_indicator = {
                "pending": "[ ]",
                "in_progress": "[~]",
                "completed": "[✓]",
            }.get(task.status.value, "[?]")

            lines.append(f"{status_indicator} [{task.id}] {task.content}")

        lines.append("")
        lines.append(
            "**Instructions**: Use TodoWrite tool to update task status as you work. Mark tasks as 'in_progress' when starting, 'completed' when finished."
        )

        return "\n".join(lines)


# Global instance for session management
_todo_manager = TodoListManager()


def get_todo_manager() -> TodoListManager:
    """Get the global TodoListManager instance."""
    return _todo_manager


def get_session_id_from_context(context=None) -> str:
    """
    Extract or generate session ID from context.
    For now, we'll use a simple approach - this can be enhanced later.
    """
    # TODO: This should be enhanced to extract session ID from investigation context
    # For now, we'll use a simple thread-local or context-based approach
    if hasattr(context, "_current_session"):
        return context._current_session

    # Generate new session ID
    session_id = str(uuid4())
    if context:
        context._current_session = session_id
    return session_id


def set_current_session_id(session_id: str) -> None:
    """Set the current session ID for this thread/context."""
    pass
    # get_session_id_from_context._current_session = session_id
