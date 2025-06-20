from holmes.core.tools import ToolsetTag
from typing import Dict, Any
from holmes.core.tools import Tool, Toolset
import datetime
from holmes.core.tools import StructuredToolResult, ToolResultStatus


class CurrentTime(Tool):
    def __init__(self):
        super().__init__(
            name="get_current_time",
            description="Return current time information. Useful to build queries that require a time information",
            parameters={},
        )

    def _invoke(self, params: Dict) -> StructuredToolResult:
        utc_now = datetime.datetime.now(datetime.timezone.utc)

        # %A provides the full weekday name (e.g., "Thursday").
        day_of_week = utc_now.strftime("%A")

        # Get the week number of the year.
        # %V provides the ISO 8601 week number (a string from "01" to "53").
        # In the ISO 8601 standard, weeks start on Monday. Week 01 is the
        # week containing the first Thursday of the year.
        week_number = utc_now.strftime("%V")

        # Get the month.
        # %B provides the full month name (e.g., "June").
        month_name = utc_now.strftime("%B")

        return StructuredToolResult(
            status=ToolResultStatus.SUCCESS,
            data=(
                f"The current UTC date and time are {utc_now}.\n"
                f"The current UTC timestamp in seconds is {int(utc_now.timestamp())}.\n"
                f"Today is {day_of_week}.\n"
                f"The month is {month_name}.\n"
                f"The week number is {week_number}."
            ),
            params=params,
        )

    def get_parameterized_one_liner(self, params) -> str:
        return "fetched current time"


class DatetimeToolset(Toolset):
    def __init__(self):
        super().__init__(
            name="datetime",
            enabled=True,
            description="Current date and time information",
            docs_url="https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/datetime.html",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/8/8b/OOjs_UI_icon_calendar-ltr.svg",
            prerequisites=[],
            tools=[CurrentTime()],
            tags=[ToolsetTag.CORE],
            is_default=True,
        )

    def get_example_config(self) -> Dict[str, Any]:
        return {}
