from typing import Dict, List, Optional
from dataclasses import dataclass
from tabulate import tabulate  # type: ignore
from litellm import completion
import textwrap


@dataclass
class TestResult:
    test_id: str
    test_name: str
    expected: str
    actual: str
    pass_fail: str
    tools_called: List[str]
    logs: str
    test_type: str = ""
    error_message: Optional[str] = None


class SummaryPlugin:
    def __init__(self):
        self.test_results: Dict[str, TestResult] = {}
        self.current_test_logs: List[str] = []

    def pytest_runtest_setup(self, item):
        """Capture test setup"""
        self.current_test_logs = []

    def pytest_runtest_call(self, item):
        """Capture test execution"""
        pass

    def pytest_runtest_teardown(self, item):
        """Capture test teardown"""
        pass

    def pytest_runtest_logreport(self, report):
        """Capture log output from each test phase"""
        if hasattr(report, "caplog") and report.caplog:
            if hasattr(report.caplog, "messages"):
                self.current_test_logs.extend(report.caplog.messages)
            elif isinstance(report.caplog, str):
                self.current_test_logs.append(report.caplog)

    def pytest_runtest_makereport(self, item, call):
        """Capture test results"""
        if call.when == "call":
            # Extract test info from item
            test_id = self._extract_test_id(item.name)
            test_name = self._extract_test_name(item.name)

            # Get captured output
            expected, actual, tools_called = self._extract_test_data(item, call)

            # Debug output
            print(
                f"[DEBUG] Plugin captured test {test_id} ({test_name}): expected='{expected[:50]}...', actual='{actual[:50]}...'"
            )

            # Determine pass/fail
            pass_fail = "✅ PASS" if call.excinfo is None else "❌ FAIL"

            # Get error message if failed
            error_message = str(call.excinfo.value) if call.excinfo else None

            # Store results for all holmes tests (ask_holmes and investigate)
            is_ask_holmes = "test_ask_holmes" in item.name
            is_investigate = "test_investigate" in item.name

            if is_ask_holmes or is_investigate:
                test_type = "ask" if is_ask_holmes else "investigate"

                # Use unique key to handle multiple tests with same ID
                unique_key = (
                    f"{test_id}_{test_name}"
                    if test_id in self.test_results
                    else test_id
                )
                self.test_results[unique_key] = TestResult(
                    test_id=test_id,
                    test_name=test_name,
                    expected=expected,
                    actual=actual,
                    pass_fail=pass_fail,
                    tools_called=tools_called,
                    logs="\n".join(self.current_test_logs),
                    test_type=test_type,
                    error_message=error_message,
                )

    def _extract_test_id(self, test_name: str) -> str:
        """Extract test ID from test name like test_ask_holmes[01_how_many_pods]"""
        if "[" in test_name and "]" in test_name:
            test_case = test_name.split("[")[1].split("]")[0]
            # Extract number from start of test case name
            return test_case.split("_")[0] if "_" in test_case else test_case
        return "unknown"

    def _extract_test_name(self, test_name: str) -> str:
        """Extract readable test name"""
        if "[" in test_name and "]" in test_name:
            test_case = test_name.split("[")[1].split("]")[0]
            # Remove number prefix and convert underscores to spaces
            parts = test_case.split("_")[1:] if "_" in test_case else [test_case]
            return "_".join(parts)
        return test_name

    def _extract_test_data(self, item, call=None) -> tuple:
        """Extract expected, actual, and tools called from test output"""
        expected = "Unknown"
        actual = "Unknown"
        tools_called = []

        # Try to get data from captured output first
        if hasattr(item, "user_properties"):
            for key, value in item.user_properties:
                if key == "expected":
                    expected = str(value)
                elif key == "actual":
                    actual = str(value)
                elif key == "tools_called":
                    tools_called = value if isinstance(value, list) else [str(value)]

        # Try to get captured stdout from pytest
        captured_stdout = ""
        if call and hasattr(call, "result"):
            if hasattr(call.result, "capstdout"):
                captured_stdout = call.result.capstdout
            elif hasattr(call.result, "sections"):
                # Look through captured sections
                for section_name, content in call.result.sections:
                    if section_name == "Captured stdout call":
                        captured_stdout = content
                        break

        # Combine all available output
        all_output = captured_stdout + "\n" + "\n".join(self.current_test_logs)

        # If not found in user_properties, try to extract from captured output
        if (expected == "Unknown" or actual == "Unknown") and all_output.strip():
            # Look for ** EXPECTED ** section
            if "** EXPECTED **" in all_output:
                lines = all_output.split("\n")
                for i, line in enumerate(lines):
                    if "** EXPECTED **" in line and i + 1 < len(lines):
                        expected_line = lines[i + 1]
                        if expected_line.startswith("-  "):
                            expected = expected_line[3:]  # Remove "-  " prefix
                        break

            # Look for ** OUTPUT ** section or try to find actual output
            if "** OUTPUT **" in all_output:
                lines = all_output.split("\n")
                for i, line in enumerate(lines):
                    if "** OUTPUT **" in line and i + 1 < len(lines):
                        actual = lines[i + 1].strip()
                        break

        return expected, actual, tools_called

    def pytest_sessionfinish(self, session):
        """Generate summary table and analysis at end of test session"""
        if not self.test_results:
            return

        print("\n" + "=" * 80)
        print("🔍 HOLMES TESTS SUMMARY")
        print("=" * 80)

        # Generate table with analysis included
        self._print_summary_table(self.test_results)

    def _print_summary_table(self, test_results: Dict[str, TestResult]):
        """Print formatted summary table"""
        import textwrap

        table_data = []
        for result in test_results.values():
            # Wrap long content for table readability
            expected_wrapped = (
                "\n".join(textwrap.wrap(result.expected, width=40))
                if result.expected
                else ""
            )
            actual_wrapped = (
                "\n".join(textwrap.wrap(result.actual, width=40))
                if result.actual
                else ""
            )

            # Add test type to ID for clarity
            test_id_with_type = f"{result.test_id} ({result.test_type})"

            # Get analysis for failed tests
            analysis = ""
            if "❌ FAIL" in result.pass_fail:
                try:
                    analysis = self._get_llm_analysis(result)
                    # Wrap analysis text for table readability
                    analysis = "\n".join(textwrap.wrap(analysis, width=50))
                except Exception as e:
                    analysis = f"Analysis failed: {str(e)}"

            table_data.append(
                [
                    test_id_with_type,
                    result.test_name,
                    expected_wrapped,
                    actual_wrapped,
                    result.pass_fail,
                    analysis,
                ]
            )

        headers = [
            "Test ID",
            "Test Name",
            "Expected",
            "Actual",
            "Pass/Fail",
            "Analysis",
        ]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def _get_llm_analysis(self, result: TestResult) -> str:
        """Get LLM analysis of test failure"""
        prompt = textwrap.dedent(f"""\
            Analyze this failed eval for an AIOps agent why it failed.
            TEST: {result.test_name}
            EXPECTED: {result.expected}
            ACTUAL: {result.actual}
            TOOLS CALLED: {', '.join(result.tools_called)}
            ERROR: {result.error_message or 'Test assertion failed'}

            LOGS:
            {result.logs if result.logs else 'No logs available'}

            Please provide a concise analysis (2-3 sentences) and categorize this as one of:
            - Problem with mock data - the test is failing due to incorrect or incomplete mock data, but the agent itself did the correct queries you would expect it to do
            - Setup issue - the test is failing due to an issue with the test setup, such as missing tools or incorrect before_test/after_test configuration
            - Real failure - the test is failing because the agent did not perform as expected, and this is a real issue that needs to be fixed
            """)

        try:
            response = completion(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Analysis failed: {e}"


def pytest_configure(config):
    """Register the plugin"""
    if not hasattr(config, "summary_plugin"):
        config.summary_plugin = SummaryPlugin()
        config.pluginmanager.register(config.summary_plugin, "summary_plugin")


def pytest_unconfigure(config):
    """Unregister the plugin"""
    if hasattr(config, "summary_plugin"):
        config.pluginmanager.unregister(config.summary_plugin)
