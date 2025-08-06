from holmes.core.tools import TodoWriteTool, ToolResultStatus, TaskStatus, TaskPriority


class TestTodoWriteTool:
    def test_todo_write_tool_creation(self):
        """Test that TodoWriteTool can be created with correct parameters."""
        tool = TodoWriteTool()
        assert tool.name == "TodoWrite"
        assert "investigation tasks" in tool.description
        assert "todos" in tool.parameters

    def test_todo_write_tool_empty_params(self):
        """Test TodoWriteTool with empty parameters."""
        tool = TodoWriteTool()
        result = tool._invoke({})

        assert result.status == ToolResultStatus.SUCCESS
        assert isinstance(result.data, str)
        assert "0 tasks" in result.data
        assert "Investigation plan updated" in result.data

    def test_todo_write_tool_with_tasks(self):
        """Test TodoWriteTool with valid task data."""
        tool = TodoWriteTool()
        params = {
            "todos": [
                {
                    "id": "1",
                    "content": "Check pod status",
                    "status": "pending",
                    "priority": "high",
                },
                {
                    "id": "2",
                    "content": "Analyze logs",
                    "status": "in_progress",
                    "priority": "medium",
                },
            ]
        }

        result = tool._invoke(params)

        assert result.status == ToolResultStatus.SUCCESS
        assert isinstance(result.data, str)
        assert "2 tasks" in result.data
        assert "Investigation plan updated" in result.data
        # Should include pretty printed TodoList
        assert "Check pod status" in result.data
        assert "Analyze logs" in result.data

    def test_todo_write_tool_default_values(self):
        """Test TodoWriteTool with minimal task data uses defaults."""
        tool = TodoWriteTool()
        params = {"todos": [{"content": "Test task"}]}

        result = tool._invoke(params)

        assert result.status == ToolResultStatus.SUCCESS
        assert isinstance(result.data, str)
        assert "1 tasks" in result.data
        assert "Investigation plan updated" in result.data
        # Should include pretty printed TodoList
        assert "Test task" in result.data

    def test_todo_write_tool_invalid_enum_values(self):
        """Test TodoWriteTool handles invalid enum values gracefully."""
        tool = TodoWriteTool()
        params = {
            "todos": [
                {
                    "content": "Test task",
                    "status": "invalid_status",
                    "priority": "invalid_priority",
                }
            ]
        }

        result = tool._invoke(params)

        # Should handle gracefully and return error
        assert result.status == ToolResultStatus.ERROR
        assert "Failed to process tasks" in result.error

    def test_get_parameterized_one_liner(self):
        """Test the parameterized one-liner description."""
        tool = TodoWriteTool()

        params = {"todos": [{"content": "task1"}, {"content": "task2"}]}
        one_liner = tool.get_parameterized_one_liner(params)
        assert "2 investigation tasks" in one_liner

        params = {"todos": []}
        one_liner = tool.get_parameterized_one_liner(params)
        assert "0 investigation tasks" in one_liner

    def test_task_status_enum(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.COMPLETED == "completed"

    def test_task_priority_enum(self):
        """Test TaskPriority enum values."""
        assert TaskPriority.HIGH == "high"
        assert TaskPriority.MEDIUM == "medium"
        assert TaskPriority.LOW == "low"

    def test_openai_format(self):
        """Test that the tool generates correct OpenAI format."""
        tool = TodoWriteTool()
        openai_format = tool.get_openai_format()

        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "TodoWrite"
        assert "investigation tasks" in openai_format["function"]["description"]

        # Check parameters schema
        params = openai_format["function"]["parameters"]
        assert params["type"] == "object"
        assert "todos" in params["properties"]

        # Check array schema has items property
        todos_param = params["properties"]["todos"]
        assert todos_param["type"] == "array"
        assert "items" in todos_param
        assert todos_param["items"]["type"] == "object"

        # Check required fields
        assert "todos" in params["required"]

    def test_session_storage_functionality(self):
        """Test that the tool stores tasks in session storage."""
        from holmes.core.todo_manager import get_todo_manager, set_current_session_id

        tool = TodoWriteTool()
        session_id = "test-session-456"
        set_current_session_id(session_id)

        params = {
            "todos": [
                {
                    "id": "1",
                    "content": "Task 1",
                    "status": "pending",
                    "priority": "high",
                },
                {
                    "id": "2",
                    "content": "Task 2",
                    "status": "completed",
                    "priority": "low",
                },
            ]
        }

        result = tool._invoke(params)

        assert result.status == ToolResultStatus.SUCCESS
        assert "2 tasks" in result.data
        assert "Investigation plan updated" in result.data

        # Check that the pretty printed TodoList is included in the response
        assert "CURRENT INVESTIGATION TASKS" in result.data
        assert "Task 1" in result.data
        assert "Task 2" in result.data
        assert "[ ]" in result.data  # pending indicator
        assert "[✓]" in result.data  # completed indicator
        assert "(HIGH)" in result.data  # priority indicator
        assert "(LOW)" in result.data  # priority indicator

        # Check session storage
        manager = get_todo_manager()
        stored_tasks = manager.get_session_tasks(session_id)
        assert len(stored_tasks) == 2
        assert stored_tasks[0].content == "Task 1"
        assert stored_tasks[1].content == "Task 2"

        # Check prompt formatting matches what's in the response
        prompt_context = manager.format_tasks_for_prompt(session_id)
        assert (
            prompt_context in result.data
        )  # The formatted tasks should be part of the response
