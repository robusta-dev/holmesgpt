import json
import logging
import re
from pathlib import Path
from typing import List, Literal, Optional, Pattern

import humanize
import requests
from pydantic import BaseModel, ValidationError, parse_obj_as, validator
from pydantic.json import pydantic_encoder
from requests.auth import HTTPBasicAuth

from holmes.core.issue import Issue
from holmes.plugins.interfaces import SourcePlugin
from holmes.plugins.utils import dict_to_markdown

from .models import PrometheusAlert, PrometheusGettableAlert


class AlertManagerSource(SourcePlugin):
    """
    Issue IDs are of the format {alert_name}-{alert_fingerprint}-{starts_at} which is both unique and allows
    quickly identifying the alertname and using it to filter on issue_id
    """

    def __init__(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        alertname: Optional[Pattern] = None,
        label: Optional[str] = None,
        filepath: Optional[Path] = None,
    ):
        super().__init__()
        self.url = url
        self.username = username
        self.password = password
        self.alertname = alertname
        self.label = label
        self.filepath = filepath

        if self.url is None and self.filepath is None:
            # we don't mention --alertmanager-file to avoid confusing users - most users wont care about it
            raise ValueError("--alertmanager-url must be specified")
        if self.url is not None and self.filepath is not None:
            logging.warning(f"Ignoring --alertmanager-url because --alertmanager-file is specified")
        if self.url and not (
            self.url.startswith("http://") or self.url.startswith("https://")
        ):
            raise ValueError("--alertmanager-url must start with http:// or https://")

    def __fetch_issues_from_api(self) -> List[PrometheusAlert]:
        fetch_alerts_url = f"{self.url}/api/v2/alerts"
        params = {
            "active": "true",
            "silenced": "false",
            "inhibited": "false",
        }
        if self.username is not None or self.password is not None:
            auth = HTTPBasicAuth(self.username, self.password)
        else:
            auth = None

        logging.info(f"Loading alerts from url {fetch_alerts_url}")
        response = requests.get(fetch_alerts_url, params=params, auth=auth)
        if response.status_code != 200:
            raise Exception(
                f"Failed to get live alerts: {response.status_code} {response.text}"
            )
        data = response.json()
        return [
            a.to_regular_prometheus_alert()
            for a in parse_obj_as(List[PrometheusGettableAlert], data)
        ]

    def __fetch_issues_from_file(self) -> List[PrometheusAlert]:
        logging.info(f"Loading alerts from file {self.filepath}")
        with open(self.filepath, "r") as f:
            data = json.load(f)
        return parse_obj_as(List[PrometheusAlert], data)

    def fetch_issues(self) -> List[Issue]:
        if self.filepath is not None:
            alerts = self.__fetch_issues_from_file()
        else:
            alerts = self.__fetch_issues_from_api()

        alerts = self.label_filter_issues(alerts)

        if self.alertname is not None:
            alertname_filter = re.compile(self.alertname)
            alerts = [a for a in alerts if alertname_filter.match(a.unique_id)]

        return [
            Issue(
                id=alert.unique_id,
                name=alert.name,
                source_type="prometheus",
                source_instance_id=self.url,
                url=alert.generatorURL,
                presentation_key_metadata=f"*Severity*: {alert.labels['severity']}\n*Start Time*: {alert.startsAt.strftime('%Y-%m-%d %H:%M:%S UTC')}\n*Duration*: {humanize.naturaldelta(alert.duration)}",
                presentation_all_metadata=self.__format_issue_metadata(alert),
                raw=alert.model_dump(),
            )
            for alert in alerts
        ]

    def dump_raw_alerts_to_file(self, path: Path) -> List[PrometheusAlert]:
        """
        Useful for generating test data
        """
        alerts = self.__fetch_issues_from_api()
        with open(path, "w") as f:
            f.write(json.dumps(alerts, default=pydantic_encoder, indent=2))

    def label_filter_issues(
        self, issues: List[PrometheusAlert]
    ) -> List[PrometheusAlert]:
        if not self.label:
            return issues

        label_parts = self.label.split("=")
        if len(label_parts) != 2:
            raise Exception(
                f"The label {self.label} is of the wrong format use '--alertmanager-label key=value'"
            )

        alert_label_key, alert_label_value = label_parts
        return [
            issue
            for issue in issues
            if issue.labels.get(alert_label_key, None) == alert_label_value
        ]

    @staticmethod
    def __format_issue_metadata(alert: PrometheusAlert) -> Optional[str]:
        if not alert.labels and not alert.annotations:
            return None
        text = ""
        if alert.labels:
            text += "*Labels:*\n"
            text += dict_to_markdown(alert.labels)
        if alert.annotations:
            text += "*Annotations:*\n"
            text += dict_to_markdown(alert.annotations)
        return text
