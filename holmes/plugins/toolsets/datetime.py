from holmes.core.tools import ToolsetTag
from typing import Dict
from holmes.core.tools import Tool, Toolset
import datetime


class CurrentTime(Tool):
    def __init__(self):
        super().__init__(
            name="get_current_time",
            description="Return current time information. Useful to build queries that require a time information",
            parameters={},
        )

    def invoke(self, params: Dict) -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        return f"The current UTC date and time are {now}. The current UTC timestamp in seconds is {int(now.timestamp())}."

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
