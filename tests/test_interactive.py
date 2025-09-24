import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from rich.console import Console
from prompt_toolkit.completion import Completion

from holmes.interactive import (
    run_interactive_loop,
    SlashCommandCompleter,
    SlashCommands,
    SmartPathCompleter,
    ConditionalExecutableCompleter,
    ShowCommandCompleter,
    handle_feedback_command,
    Feedback,
    UserFeedback,
)
from holmes.core.feedback import FeedbackMetadata
from holmes.core.tool_calling_llm import ToolCallingLLM
from tests.mocks.toolset_mocks import SampleToolset


class TestSlashCommandCompleter(unittest.TestCase):
    def test_init_without_unsupported_commands(self):
        """Test SlashCommandCompleter initialization without unsupported commands."""
        completer = SlashCommandCompleter()
        expected_commands = {cmd.command: cmd.description for cmd in SlashCommands}
        self.assertEqual(completer.commands, expected_commands)

    def test_init_with_unsupported_commands(self):
        """Test SlashCommandCompleter initialization with unsupported commands."""
        unsupported = [SlashCommands.FEEDBACK.command]
        completer = SlashCommandCompleter(unsupported)

        expected_commands = {cmd.command: cmd.description for cmd in SlashCommands}
        expected_commands.pop(SlashCommands.FEEDBACK.command)

        self.assertEqual(completer.commands, expected_commands)

    def test_get_completions_with_slash_prefix(self):
        """Test completion suggestions for slash commands."""
        completer = SlashCommandCompleter()
        document = Mock()
        document.text_before_cursor = "/ex"

        completions = list(completer.get_completions(document, None))

        self.assertEqual(len(completions), 1)
        self.assertEqual(completions[0].text, SlashCommands.EXIT.command)

    def test_get_completions_without_slash_prefix(self):
        """Test no completions for non-slash input."""
        completer = SlashCommandCompleter()
        document = Mock()
        document.text_before_cursor = "regular input"

        completions = list(completer.get_completions(document, None))

        self.assertEqual(len(completions), 0)

    def test_get_completions_filters_unsupported_commands(self):
        """Test that unsupported commands are filtered out of completions."""
        unsupported = [SlashCommands.FEEDBACK.command]
        completer = SlashCommandCompleter(unsupported)
        document = Mock()
        document.text_before_cursor = "/feed"

        completions = list(completer.get_completions(document, None))

        self.assertEqual(len(completions), 0)


class TestHandleFeedbackCommand(unittest.TestCase):
    @patch('holmes.interactive.PromptSession')
    def test_handle_feedback_command_positive(self, mock_prompt_session_class):
        """Test feedback command with positive rating."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["y", "Great response!"]

        console = Mock()
        style = Mock()

        result = handle_feedback_command(mock_session, style, console)

        self.assertIsInstance(result, UserFeedback)
        self.assertTrue(result.is_positive)
        self.assertEqual(result.comment, "Great response!")

    @patch('holmes.interactive.PromptSession')
    def test_handle_feedback_command_negative(self, mock_prompt_session_class):
        """Test feedback command with negative rating."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["n", "Could be better"]

        console = Mock()
        style = Mock()

        result = handle_feedback_command(mock_session, style, console)

        self.assertIsInstance(result, UserFeedback)
        self.assertFalse(result.is_positive)
        self.assertEqual(result.comment, "Could be better")

    @patch('holmes.interactive.PromptSession')
    def test_handle_feedback_command_no_comment(self, mock_prompt_session_class):
        """Test feedback command without comment."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["y", ""]

        console = Mock()
        style = Mock()

        result = handle_feedback_command(mock_session, style, console)

        self.assertIsInstance(result, UserFeedback)
        self.assertTrue(result.is_positive)
        self.assertIsNone(result.comment)


class TestRunInteractiveLoop(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_ai = Mock(spec=ToolCallingLLM)
        self.mock_ai.llm = Mock()
        self.mock_ai.llm.model = "test-model"
        self.mock_ai.llm.get_context_window_size.return_value = 4096
        self.mock_ai.tool_executor = Mock()
        self.mock_ai.tool_executor.toolsets = [SampleToolset()]

        # Mock AI response
        self.mock_response = Mock()
        self.mock_response.result = "Test response"
        self.mock_response.messages = []
        self.mock_response.tool_calls = []
        self.mock_ai.call.return_value = self.mock_response

        self.mock_console = Mock(spec=Console)

        # Create a temporary directory for history file
        self.temp_dir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.temp_dir, "history")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('holmes.interactive.check_version_async')
    @patch('holmes.interactive.PromptSession')
    @patch('holmes.interactive.build_initial_ask_messages')
    @patch('holmes.interactive.config_path_dir', new_callable=lambda: tempfile.gettempdir())
    @patch('holmes.interactive.handle_feedback_command')
    def test_run_interactive_loop_feedback_command_positive_with_callback(self, mock_handle_feedback,
                                                                          mock_config_dir,
                                                                          mock_build_messages,
                                                                          mock_prompt_session_class,
                                                                          mock_check_version):
        """Test interactive loop with /feedback command - positive feedback."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["/feedback", "/exit"]

        mock_build_messages.return_value = []
        mock_callback = Mock()

        # Mock the feedback handler to return positive feedback
        mock_user_feedback = UserFeedback(is_positive=True, comment="Great response!")
        mock_handle_feedback.return_value = mock_user_feedback

        # Run the interactive loop
        run_interactive_loop(
            ai=self.mock_ai,
            console=self.mock_console,
            initial_user_input=None,
            include_files=None,
            post_processing_prompt=None,
            show_tool_output=False,
            check_version=False,
            feedback_callback=mock_callback,
        )

        # Verify feedback handler was called
        mock_handle_feedback.assert_called_once()

        # Verify callback was called with complete Feedback object
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args[0][0]
        
        # Test complete Feedback structure
        self.assertIsInstance(call_args, Feedback)
        
        # Test UserFeedback component
        self.assertIsNotNone(call_args.user_feedback)
        self.assertIsInstance(call_args.user_feedback, UserFeedback)
        self.assertEqual(call_args.user_feedback.is_positive, True)
        self.assertEqual(call_args.user_feedback.comment, "Great response!")
        
        # Test FeedbackMetadata component
        self.assertIsNotNone(call_args.metadata)
        self.assertIsInstance(call_args.metadata, FeedbackMetadata)
        
        # Test LLM information in metadata
        self.assertIsNotNone(call_args.metadata.llm)
        self.assertEqual(call_args.metadata.llm.model, "test-model")
        self.assertEqual(call_args.metadata.llm.max_context_size, 4096)
        
        # Test LLM responses list (should be empty initially but list should exist)
        self.assertIsInstance(call_args.metadata.llm_responses, list)
        
        # Test to_dict() functionality
        feedback_dict = call_args.to_dict()
        self.assertIn('user_feedback', feedback_dict)
        self.assertIn('metadata', feedback_dict)
        self.assertEqual(feedback_dict['user_feedback']['is_positive'], True)
        self.assertEqual(feedback_dict['user_feedback']['comment'], "Great response!")
        self.assertEqual(feedback_dict['metadata']['llm']['model'], "test-model")
        self.assertEqual(feedback_dict['metadata']['llm']['max_context_size'], 4096)

    @patch('holmes.interactive.check_version_async')
    @patch('holmes.interactive.PromptSession')
    @patch('holmes.interactive.build_initial_ask_messages')
    @patch('holmes.interactive.config_path_dir', new_callable=lambda: tempfile.gettempdir())
    @patch('holmes.interactive.handle_feedback_command')
    def test_run_interactive_loop_feedback_command_negative_with_callback(self, mock_handle_feedback,
                                                                          mock_config_dir,
                                                                          mock_build_messages,
                                                                          mock_prompt_session_class,
                                                                          mock_check_version):
        """Test interactive loop with /feedback command - negative feedback."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["/feedback", "/exit"]

        mock_build_messages.return_value = []
        mock_callback = Mock()

        # Mock the feedback handler to return negative feedback
        mock_user_feedback = UserFeedback(is_positive=False, comment="Could be better")
        mock_handle_feedback.return_value = mock_user_feedback

        # Run the interactive loop
        run_interactive_loop(
            ai=self.mock_ai,
            console=self.mock_console,
            initial_user_input=None,
            include_files=None,
            post_processing_prompt=None,
            show_tool_output=False,
            check_version=False,
            feedback_callback=mock_callback,
        )

        # Verify callback was called with complete Feedback object containing negative feedback
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args[0][0]
        
        # Test complete Feedback structure
        self.assertIsInstance(call_args, Feedback)
        
        # Test UserFeedback component
        self.assertIsNotNone(call_args.user_feedback)
        self.assertIsInstance(call_args.user_feedback, UserFeedback)
        self.assertEqual(call_args.user_feedback.is_positive, False)
        self.assertEqual(call_args.user_feedback.comment, "Could be better")
        
        # Test FeedbackMetadata component
        self.assertIsNotNone(call_args.metadata)
        self.assertIsInstance(call_args.metadata, FeedbackMetadata)
        
        # Test LLM information in metadata
        self.assertIsNotNone(call_args.metadata.llm)
        self.assertEqual(call_args.metadata.llm.model, "test-model")
        self.assertEqual(call_args.metadata.llm.max_context_size, 4096)
        
        # Test LLM responses list
        self.assertIsInstance(call_args.metadata.llm_responses, list)
        
        # Test to_dict() functionality for negative feedback
        feedback_dict = call_args.to_dict()
        self.assertIn('user_feedback', feedback_dict)
        self.assertIn('metadata', feedback_dict)
        self.assertEqual(feedback_dict['user_feedback']['is_positive'], False)
        self.assertEqual(feedback_dict['user_feedback']['comment'], "Could be better")
        self.assertEqual(feedback_dict['metadata']['llm']['model'], "test-model")
        self.assertEqual(feedback_dict['metadata']['llm']['max_context_size'], 4096)
        self.assertIsInstance(feedback_dict['metadata']['llm_responses'], list)

    @patch('holmes.interactive.check_version_async')
    @patch('holmes.interactive.PromptSession')
    @patch('holmes.interactive.build_initial_ask_messages')
    @patch('holmes.interactive.config_path_dir', new_callable=lambda: tempfile.gettempdir())
    @patch('holmes.interactive.handle_feedback_command')
    def test_run_interactive_loop_feedback_with_conversation_history(self, mock_handle_feedback,
                                                                     mock_config_dir,
                                                                     mock_build_messages,
                                                                     mock_prompt_session_class,
                                                                     mock_check_version):
        """Test feedback system with conversation history (LLM responses)."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["What is Kubernetes?", "/feedback", "/exit"]

        mock_build_messages.return_value = [{"role": "user", "content": "What is Kubernetes?"}]
        mock_callback = Mock()

        # Mock the feedback handler to return feedback
        mock_user_feedback = UserFeedback(is_positive=True, comment="Very helpful!")
        mock_handle_feedback.return_value = mock_user_feedback

        # Mock tracer for the normal query
        mock_tracer = Mock()
        mock_trace_span = Mock()
        mock_tracer.start_trace.return_value.__enter__ = Mock(return_value=mock_trace_span)
        mock_tracer.start_trace.return_value.__exit__ = Mock(return_value=None)
        mock_tracer.get_trace_url.return_value = None

        # Run the interactive loop with a conversation
        run_interactive_loop(
            ai=self.mock_ai,
            console=self.mock_console,
            initial_user_input=None,
            include_files=None,
            post_processing_prompt=None,
            show_tool_output=False,
            check_version=False,
            feedback_callback=mock_callback,
            tracer=mock_tracer,
        )

        # Verify callback was called with Feedback containing conversation history
        mock_callback.assert_called_once()
        call_args = mock_callback.call_args[0][0]
        
        # Test complete Feedback structure with conversation history
        self.assertIsInstance(call_args, Feedback)
        
        # Test UserFeedback component
        self.assertIsNotNone(call_args.user_feedback)
        self.assertEqual(call_args.user_feedback.is_positive, True)
        self.assertEqual(call_args.user_feedback.comment, "Very helpful!")
        
        # Test FeedbackMetadata with LLM responses
        self.assertIsNotNone(call_args.metadata)
        self.assertIsInstance(call_args.metadata, FeedbackMetadata)
        
        # Test LLM information
        self.assertEqual(call_args.metadata.llm.model, "test-model")
        self.assertEqual(call_args.metadata.llm.max_context_size, 4096)
        
        # Test LLM responses list contains the conversation
        self.assertIsInstance(call_args.metadata.llm_responses, list)
        self.assertGreaterEqual(len(call_args.metadata.llm_responses), 1)  # Should have at least one exchange
        
        # Test to_dict() functionality with conversation history
        feedback_dict = call_args.to_dict()
        self.assertIn('metadata', feedback_dict)
        self.assertIn('llm_responses', feedback_dict['metadata'])
        self.assertIsInstance(feedback_dict['metadata']['llm_responses'], list)
        
        # If there are responses, verify their structure
        if feedback_dict['metadata']['llm_responses']:
            first_response = feedback_dict['metadata']['llm_responses'][0]
            self.assertIn('user_ask', first_response)
            self.assertIn('response', first_response)
            self.assertIsInstance(first_response['user_ask'], str)
            self.assertIsInstance(first_response['response'], str)

    @patch('holmes.interactive.check_version_async')
    @patch('holmes.interactive.PromptSession')
    @patch('holmes.interactive.build_initial_ask_messages')
    @patch('holmes.interactive.config_path_dir', new_callable=lambda: tempfile.gettempdir())
    def test_run_interactive_loop_feedback_command_without_callback(self, mock_config_dir,
                                                                    mock_build_messages,
                                                                    mock_prompt_session_class,
                                                                    mock_check_version):
        """Test interactive loop with /feedback command when no callback is provided."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["/feedback", "/exit"]

        mock_build_messages.return_value = []

        # Run the interactive loop without feedback callback
        run_interactive_loop(
            ai=self.mock_ai,
            console=self.mock_console,
            initial_user_input=None,
            include_files=None,
            post_processing_prompt=None,
            show_tool_output=False,
            check_version=False,
            feedback_callback=None,  # No callback
        )

        # Verify "Unknown command" message was displayed
        unknown_calls = [call_args for call_args in self.mock_console.print.call_args_list
                         if "Unknown command" in str(call_args)]
        self.assertTrue(len(unknown_calls) > 0)

    @patch('holmes.interactive.check_version_async')
    @patch('holmes.interactive.PromptSession')
    @patch('holmes.interactive.build_initial_ask_messages')
    @patch('holmes.interactive.config_path_dir', new_callable=lambda: tempfile.gettempdir())
    def test_run_interactive_loop_feedback_help_filtering(self, mock_config_dir,
                                                          mock_build_messages,
                                                          mock_prompt_session_class,
                                                          mock_check_version):
        """Test that help command filters out feedback when callback is None."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["/help", "/exit"]

        mock_build_messages.return_value = []

        # Run without feedback callback
        run_interactive_loop(
            ai=self.mock_ai,
            console=self.mock_console,
            initial_user_input=None,
            include_files=None,
            post_processing_prompt=None,
            show_tool_output=False,
            check_version=False,
            feedback_callback=None,
        )

        # Check all printed messages
        all_prints = [str(call_args) for call_args in self.mock_console.print.call_args_list]

        # Should contain help for other commands but not feedback
        has_help_command = any("/help" in print_msg for print_msg in all_prints)
        has_exit_command = any("/exit" in print_msg for print_msg in all_prints)
        has_feedback_command = any("/feedback" in print_msg for print_msg in all_prints)

        self.assertTrue(has_help_command)
        self.assertTrue(has_exit_command)
        self.assertFalse(has_feedback_command)  # Should be filtered out

    @patch('holmes.interactive.check_version_async')
    @patch('holmes.interactive.PromptSession')
    @patch('holmes.interactive.build_initial_ask_messages')
    @patch('holmes.interactive.config_path_dir', new_callable=lambda: tempfile.gettempdir())
    def test_run_interactive_loop_feedback_help_not_filtering_with_callback(self, mock_config_dir,
                                                                            mock_build_messages,
                                                                            mock_prompt_session_class,
                                                                            mock_check_version):
        """Test that help command shows feedback when callback is provided."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["/help", "/exit"]

        mock_build_messages.return_value = []
        mock_callback = Mock()

        # Run with feedback callback
        run_interactive_loop(
            ai=self.mock_ai,
            console=self.mock_console,
            initial_user_input=None,
            include_files=None,
            post_processing_prompt=None,
            show_tool_output=False,
            check_version=False,
            feedback_callback=mock_callback,
        )

        # Check all printed messages
        all_prints = [str(call_args) for call_args in self.mock_console.print.call_args_list]

        # Should contain help for feedback command
        has_feedback_command = any("/feedback" in print_msg for print_msg in all_prints)
        self.assertTrue(has_feedback_command)  # Should be shown

    @patch('holmes.interactive.check_version_async')
    @patch('holmes.interactive.PromptSession')
    @patch('holmes.interactive.build_initial_ask_messages')
    @patch('holmes.interactive.config_path_dir', new_callable=lambda: tempfile.gettempdir())
    def test_run_interactive_loop_with_initial_input(self, mock_config_dir, mock_build_messages,
                                                     mock_prompt_session_class, mock_check_version):
        """Test interactive loop with initial user input."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        mock_session.prompt.side_effect = ["/exit"]  # Only need exit after initial input

        initial_input = "What is kubernetes?"
        mock_build_messages.return_value = [{"role": "user", "content": initial_input}]

        # Mock tracer
        mock_tracer = Mock()
        mock_trace_span = Mock()
        mock_tracer.start_trace.return_value.__enter__ = Mock(return_value=mock_trace_span)
        mock_tracer.start_trace.return_value.__exit__ = Mock(return_value=None)
        mock_tracer.get_trace_url.return_value = None

        # Run the interactive loop
        run_interactive_loop(
            ai=self.mock_ai,
            console=self.mock_console,
            initial_user_input=initial_input,
            include_files=None,
            post_processing_prompt=None,
            show_tool_output=False,
            check_version=False,
            tracer=mock_tracer,
        )

        # Verify initial input was displayed
        initial_calls = [call_args for call_args in self.mock_console.print.call_args_list
                         if initial_input in str(call_args)]
        self.assertTrue(len(initial_calls) > 0)

        # Verify AI was called with initial input
        self.mock_ai.call.assert_called_once()

    @patch('holmes.interactive.check_version_async')
    @patch('holmes.interactive.PromptSession')
    @patch('holmes.interactive.build_initial_ask_messages')
    @patch('holmes.interactive.config_path_dir', new_callable=lambda: tempfile.gettempdir())
    def test_run_interactive_loop_exception_handling(self, mock_config_dir, mock_build_messages,
                                                     mock_prompt_session_class, mock_check_version):
        """Test interactive loop exception handling."""
        mock_session = Mock()
        mock_prompt_session_class.return_value = mock_session
        # First call raises exception, second call exits
        mock_session.prompt.side_effect = [Exception("Test error"), "/exit"]

        mock_build_messages.return_value = []

        # Run the interactive loop
        run_interactive_loop(
            ai=self.mock_ai,
            console=self.mock_console,
            initial_user_input=None,
            include_files=None,
            post_processing_prompt=None,
            show_tool_output=False,
            check_version=False,
        )

        # Verify error was displayed
        error_calls = [call_args for call_args in self.mock_console.print.call_args_list
                       if "Error:" in str(call_args)]
        self.assertTrue(len(error_calls) > 0)

    def test_run_interactive_loop_unsupported_commands_without_callback(self):
        """Test that feedback command is not available when callback is None."""
        with patch('holmes.interactive.check_version_async'), \
                patch('holmes.interactive.PromptSession') as mock_prompt_session_class, \
                patch('holmes.interactive.build_initial_ask_messages'), \
                patch('holmes.interactive.config_path_dir', return_value=tempfile.gettempdir()):

            mock_session = Mock()
            mock_prompt_session_class.return_value = mock_session
            mock_session.prompt.side_effect = ["/help", "/exit"]

            # Run the interactive loop without feedback callback
            run_interactive_loop(
                ai=self.mock_ai,
                console=self.mock_console,
                initial_user_input=None,
                include_files=None,
                post_processing_prompt=None,
                show_tool_output=False,
                check_version=False,
                feedback_callback=None,  # No callback
            )

            # Verify feedback command is not shown in help
            help_calls = [str(call_args) for call_args in self.mock_console.print.call_args_list]

            # The feedback command should not be shown since callback is None
            has_feedback_in_help = any("/feedback" in call_str for call_str in help_calls)
            self.assertFalse(has_feedback_in_help)
