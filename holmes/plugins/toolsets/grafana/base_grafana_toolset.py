import logging
from typing import Any, ClassVar, Type, Tuple
from holmes.core.tools.tools import (
    Tool,
    Toolset,
    ToolsetTag,
    CallablePrerequisite,
)
from holmes.plugins.toolsets.grafana.common import GrafanaConfig
from holmes.plugins.toolsets.grafana.grafana_api import get_health
from holmes.core.tools.tools_utils import TOOLSET_CONFIG_MISSING_ERROR


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

    def prerequisites_callable(self, config: dict[str, Any]) -> Tuple[bool, str]:
        if not config:
            logging.warning(f"Grafana config not provided {self.name}")
            return False, TOOLSET_CONFIG_MISSING_ERROR

        try:
            self._grafana_config = self.config_class(**config)
            return get_health(self._grafana_config)

        except Exception as e:
            logging.exception(f"Failed to set up grafana toolset {self.name}")
            return False, str(e)

    def get_example_config(self):
        example_config = GrafanaConfig(
            api_key="YOUR API KEY",
            url="YOUR GRAFANA URL",
            grafana_datasource_uid="UID OF DATASOURCE IN GRAFANA",
        )
        return example_config.model_dump()
