from holmes.core.todo_manager import (
    TodoListManager,
    get_todo_manager,
)
from holmes.plugins.toolsets.investigator.model import Task, TaskStatus


class TestTodoListManager:
    def test_manager_creation(self):
        """Test that TodoListManager can be created."""
        manager = TodoListManager()
        assert manager.get_session_count() == 0

    def test_empty_session(self):
        """Test handling of empty session."""
        manager = TodoListManager()
        tasks = manager.get_session_tasks("non-existent-session")
        assert tasks == []

        prompt_context = manager.format_tasks_for_prompt("non-existent-session")
        assert prompt_context == ""

    def test_session_task_management(self):
        """Test adding and retrieving tasks from session."""
        manager = TodoListManager()
        session_id = "test-session"

        # Create test tasks
        tasks = [
            Task(id="1", content="Task 1", status=TaskStatus.PENDING),
            Task(id="2", content="Task 2", status=TaskStatus.IN_PROGRESS),
            Task(id="3", content="Task 3", status=TaskStatus.COMPLETED),
        ]

        # Update session tasks
        manager.update_session_tasks(session_id, tasks)
        assert manager.get_session_count() == 1

        # Retrieve tasks
        retrieved_tasks = manager.get_session_tasks(session_id)
        assert len(retrieved_tasks) == 3
        assert retrieved_tasks[0].content == "Task 1"
        assert retrieved_tasks[1].content == "Task 2"
        assert retrieved_tasks[2].content == "Task 3"

    def test_prompt_formatting(self):
        """Test that tasks are formatted correctly for prompt injection."""
        manager = TodoListManager()
        session_id = "test-prompt-session"

        tasks = [
            Task(id="1", content="Check system", status=TaskStatus.PENDING),
            Task(id="2", content="Review logs", status=TaskStatus.IN_PROGRESS),
            Task(id="3", content="Write report", status=TaskStatus.COMPLETED),
        ]

        manager.update_session_tasks(session_id, tasks)
        prompt_context = manager.format_tasks_for_prompt(session_id)

        # Check structure
        assert "# CURRENT INVESTIGATION TASKS" in prompt_context
        assert (
            "**Task Status**: 1 completed, 1 in progress, 1 pending" in prompt_context
        )

        # Check tasks appear
        assert "Check system" in prompt_context
        assert "Review logs" in prompt_context
        assert "Write report" in prompt_context

        # Check indicators
        assert "[ ]" in prompt_context  # pending
        assert "[~]" in prompt_context  # in_progress
        assert "[✓]" in prompt_context  # completed

        # Check priority
        assert "(HIGH)" in prompt_context
        assert "(MED)" in prompt_context
        assert "(LOW)" in prompt_context

    def test_session_clearing(self):
        """Test clearing session tasks."""
        manager = TodoListManager()
        session_id = "test-clear-session"

        tasks = [Task(id="1", content="Task 1", status=TaskStatus.PENDING)]
        manager.update_session_tasks(session_id, tasks)
        assert manager.get_session_count() == 1

        manager.clear_session(session_id)
        assert manager.get_session_count() == 0
        assert manager.get_session_tasks(session_id) == []

    def test_global_manager_instance(self):
        """Test that get_todo_manager returns the same instance."""
        manager1 = get_todo_manager()
        manager2 = get_todo_manager()
        assert manager1 is manager2
