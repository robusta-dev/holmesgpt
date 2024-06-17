import re
from typing import List, Literal, Optional, Pattern

import humanize
import requests
from pydantic import BaseModel, ValidationError, parse_obj_as, validator
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
        label: Optional[str] = None
    ):
        super().__init__()
        self.url = url
        self.username = username
        self.password = password
        self.alertname = alertname
        self.label = label

    def fetch_issues(self) -> List[Issue]:
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

        response = requests.get(fetch_alerts_url, params=params, auth=auth)
        if response.status_code != 200:
            raise Exception(
                f"Failed to get live alerts: {response.status_code} {response.text}"
            )
        data = response.json()

        alerts = [
            a.to_regular_prometheus_alert()
            for a in parse_obj_as(List[PrometheusGettableAlert], data)
        ]

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

    def label_filter_issues(self, issues: List[PrometheusAlert]) -> List[PrometheusAlert]: 
        if not self.label:
            return issues

        label_parts = self.label.split('=')
        if len(label_parts) != 2:
            raise Exception(f"The label {self.label} is of the wrong format use '--alertmanager-label key=value'")

        alert_label_key, alert_label_value = label_parts
        return [issue for issue in issues if issue.labels.get(alert_label_key, None) == alert_label_value]

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
