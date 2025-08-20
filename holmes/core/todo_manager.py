from typing import Dict, List
from threading import Lock

from holmes.plugins.toolsets.investigator.model import Task, TaskStatus


class TodoListManager:
    """
    Session-based storage manager for investigation TodoLists.
    Stores TodoLists per session and provides methods to get/update tasks.
    """

    def __init__(self):
        self._sessions: Dict[str, List[Task]] = {}
        self._lock: Lock = Lock()

    def get_session_tasks(self, session_id: str) -> List[Task]:
        with self._lock:
            return self._sessions.get(session_id, []).copy()

    def update_session_tasks(self, session_id: str, tasks: List[Task]) -> None:
        with self._lock:
            self._sessions[session_id] = tasks.copy()

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def get_session_count(self) -> int:
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

        status_order = {
            TaskStatus.PENDING: 0,
            TaskStatus.IN_PROGRESS: 1,
            TaskStatus.COMPLETED: 2,
        }

        sorted_tasks = sorted(
            tasks,
            key=lambda t: (status_order.get(t.status, 3),),
        )

        lines = ["# CURRENT INVESTIGATION TASKS"]
        lines.append("")

        pending_count = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
        progress_count = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
        completed_count = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)

        lines.append(
            f"**Task Status**: {completed_count} completed, {progress_count} in progress, {pending_count} pending"
        )
        lines.append("")

        for task in sorted_tasks:
            status_indicator = {
                TaskStatus.PENDING: "[ ]",
                TaskStatus.IN_PROGRESS: "[~]",
                TaskStatus.COMPLETED: "[✓]",
            }.get(task.status, "[?]")

            lines.append(f"{status_indicator} [{task.id}] {task.content}")

        lines.append("")
        lines.append(
            "**Instructions**: Use TodoWrite tool to update task status as you work. Mark tasks as 'in_progress' when starting, 'completed' when finished."
        )

        return "\n".join(lines)


_todo_manager = TodoListManager()


def get_todo_manager() -> TodoListManager:
    return _todo_manager
