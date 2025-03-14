import logging
from typing import Any, ClassVar, Type
from holmes.core.tools import (
    Tool,
    Toolset,
    ToolsetTag,
    CallablePrerequisite,
    ToolsetStatusEnum,
)
from holmes.plugins.toolsets.grafana.common import GrafanaConfig
from holmes.plugins.toolsets.grafana.grafana_api import get_health


class BaseGrafanaToolset(Toolset):
    config_class: ClassVar[Type[GrafanaConfig]] = GrafanaConfig

    def __init__(
        self,
        name: str,
        description: str,
        icon_url: str,
        tools: list[Tool],
        docs_url: str,
    ):
        super().__init__(
            name=name,
            description=description,
            icon_url=icon_url,
            docs_url=docs_url,
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=tools,
            tags=[
                ToolsetTag.CORE,
            ],
            enabled=False,
        )

    def prerequisites_callable(self, config: dict[str, Any]) -> bool:
        if not config:
            logging.debug("Grafana config not provided")
            self._error = "Required Grafana configuration missing"
            self._status = ToolsetStatusEnum.DISABLED
            self._checked = True
            return False

        try:
            self._grafana_config = self.config_class(**config)
            is_healthy = get_health(
                self._grafana_config.url, self._grafana_config.api_key
            )
            return is_healthy

        except Exception as e:
            # Log detailed error at DEBUG level
            logging.debug("Grafana toolset error details:", exc_info=e)
            # Store error message in the toolset object for later display
            self._error = f"{type(e).__name__}. Use -vv for details."
            self._status = ToolsetStatusEnum.FAILED
            self._checked = True
            return False

    def get_example_config(self):
        example_config = GrafanaConfig(
            api_key="YOUR API KEY",
            url="YOUR GRAFANA URL",
            grafana_datasource_uid="UID OF DATASOURCE IN GRAFANA",
        )
        return example_config.model_dump()
