from typing import Dict, List, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from litellm import completion
import textwrap
import time


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
    execution_time: Optional[float] = None


class SummaryPlugin:
    def __init__(self):
        self.test_results: Dict[str, TestResult] = {}
        self.current_test_logs: List[str] = []
        self.test_start_times: Dict[str, float] = {}

    def pytest_runtest_setup(self, item):
        """Capture test setup"""
        self.current_test_logs = []
        # Record test start time
        self.test_start_times[item.nodeid] = time.time()

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

            # Calculate execution time
            execution_time = None
            if item.nodeid in self.test_start_times:
                execution_time = time.time() - self.test_start_times[item.nodeid]

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
                    execution_time=execution_time,
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
        try:
            if "[" in test_name and "]" in test_name:
                test_case = test_name.split("[")[1].split("]")[0]
                # Remove number prefix and convert underscores to spaces
                parts = test_case.split("_")[1:] if "_" in test_case else [test_case]
                return "_".join(parts)
        except (IndexError, AttributeError):
            pass
        return test_name

    def _extract_test_data(self, item, call=None) -> tuple:
        """Extract expected, actual, and tools called from user_properties"""
        expected = "Unknown"
        actual = "Unknown"
        tools_called = []

        # Get data from user_properties set by test functions
        if hasattr(item, "user_properties"):
            for key, value in item.user_properties:
                if key == "expected":
                    expected = str(value)
                elif key == "actual":
                    actual = str(value)
                elif key == "tools_called":
                    tools_called = value if isinstance(value, list) else [str(value)]

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
        """Print formatted summary table using Rich"""
        console = Console()

        table = Table(
            title="🔍 HOLMES TESTS SUMMARY",
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
        )

        # Add columns with specific widths
        table.add_column("Test", style="cyan", width=30)
        table.add_column("Status", justify="center", width=6)
        table.add_column("Time", justify="right", width=8)
        table.add_column("Expected", style="green", width=40)
        table.add_column("Actual", style="yellow", width=40)
        table.add_column("Analysis", style="red", width=50)

        for result in test_results.values():
            # Wrap long content for table readability
            expected_wrapped = (
                "\n".join(textwrap.wrap(result.expected, width=38))
                if result.expected
                else ""
            )
            actual_wrapped = (
                "\n".join(textwrap.wrap(result.actual, width=38))
                if result.actual
                else ""
            )

            # Combine test ID and name
            combined_test_name = (
                f"{result.test_id}: {result.test_name} ({result.test_type})"
            )
            # Wrap test name to fit column
            test_name_wrapped = "\n".join(textwrap.wrap(combined_test_name, width=28))

            # Convert pass/fail to check/x status with colors
            if "PASS" in result.pass_fail:
                status = "[green]✓[/green]"
            else:
                status = "[red]✗[/red]"

            # Format execution time
            time_str = (
                f"{result.execution_time:.1f}s" if result.execution_time else "N/A"
            )

            # Get analysis for failed tests
            analysis = ""
            if "PASS" not in result.pass_fail:
                try:
                    analysis = self._get_llm_analysis(result)
                    # Wrap analysis text for table readability
                    analysis = "\n".join(textwrap.wrap(analysis, width=48))
                except Exception as e:
                    analysis = f"Analysis failed: {str(e)}"

            table.add_row(
                test_name_wrapped,
                status,
                time_str,
                expected_wrapped,
                actual_wrapped,
                analysis,
            )

        console.print(table)

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
