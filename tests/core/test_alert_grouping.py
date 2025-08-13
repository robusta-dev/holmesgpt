"""
Tests for the alert grouping system.
"""

from unittest.mock import Mock, patch

import pytest

from holmes.core.alert_grouping import (
    SmartAlertGrouper,
    AlertGroup,
    Rule,
    Condition,
)
from holmes.core.issue import Issue


@pytest.fixture
def mock_ai():
    """Mock AI for testing"""
    ai = Mock()
    ai.llm = Mock()
    ai.investigate = Mock()
    return ai


@pytest.fixture
def mock_console():
    """Mock console for testing"""
    console = Mock()
    console.print = Mock()
    return console


@pytest.fixture
def sample_alerts():
    """Sample alerts for testing"""
    return [
        Issue(
            id="alert-1",
            name="HighMemoryUsage",
            source_type="prometheus",
            source_instance_id="test",
            raw={
                "labels": {
                    "alertname": "HighMemoryUsage",
                    "service": "api",
                    "namespace": "production",
                    "severity": "warning",
                },
                "annotations": {"description": "Memory usage is above 80%"},
                "startsAt": "2024-01-01T00:00:00Z",
            },
        ),
        Issue(
            id="alert-2",
            name="PodOOMKilled",
            source_type="prometheus",
            source_instance_id="test",
            raw={
                "labels": {
                    "alertname": "PodOOMKilled",
                    "service": "api",
                    "namespace": "production",
                    "severity": "critical",
                },
                "annotations": {"description": "Pod was OOM killed"},
                "startsAt": "2024-01-01T00:05:00Z",
            },
        ),
        Issue(
            id="alert-3",
            name="DatabaseConnectionTimeout",
            source_type="prometheus",
            source_instance_id="test",
            raw={
                "labels": {
                    "alertname": "DatabaseConnectionTimeout",
                    "service": "database",
                    "namespace": "production",
                    "severity": "critical",
                },
                "annotations": {"description": "Database connection timeout"},
                "startsAt": "2024-01-01T00:10:00Z",
            },
        ),
    ]


class TestSmartAlertGrouper:
    def test_init(self, mock_ai, mock_console):
        """Test grouper initialization"""
        grouper = SmartAlertGrouper(mock_ai, mock_console, verify_first_n=3)
        assert grouper.ai == mock_ai
        assert grouper.console == mock_console
        assert grouper.verify_first_n == 3
        assert grouper.groups == []
        assert grouper.rules == []

    def test_matches_rule(self, mock_ai, mock_console, sample_alerts):
        """Test rule matching logic"""
        grouper = SmartAlertGrouper(mock_ai, mock_console)

        # Create a rule that matches service=api
        rule = Rule(
            group_id="group-1",
            conditions=[
                Condition(field="labels.service", operator="equals", value="api"),
                Condition(
                    field="labels.namespace", operator="equals", value="production"
                ),
            ],
            explanation="Matches API service in production",
        )

        # Should match first two alerts (api service)
        assert grouper._matches_rule(sample_alerts[0], rule) is True
        assert grouper._matches_rule(sample_alerts[1], rule) is True
        # Should not match third alert (database service)
        assert grouper._matches_rule(sample_alerts[2], rule) is False

    def test_check_condition_operators(self, mock_ai, mock_console, sample_alerts):
        """Test different condition operators"""
        grouper = SmartAlertGrouper(mock_ai, mock_console)
        alert = sample_alerts[0]

        # Test equals
        cond = Condition(field="labels.service", operator="equals", value="api")
        assert grouper._check_condition(alert, cond) is True

        # Test contains
        cond = Condition(
            field="annotations.description", operator="contains", value="Memory"
        )
        assert grouper._check_condition(alert, cond) is True

        # Test in
        cond = Condition(
            field="labels.severity", operator="in", value=["warning", "critical"]
        )
        assert grouper._check_condition(alert, cond) is True

        # Test exists
        cond = Condition(field="labels.service", operator="exists", value=True)
        assert grouper._check_condition(alert, cond) is True

        # Test regex
        cond = Condition(field="labels.alertname", operator="regex", value="High.*")
        assert grouper._check_condition(alert, cond) is True

    def test_get_field_value(self, mock_ai, mock_console, sample_alerts):
        """Test field value extraction with dot notation"""
        grouper = SmartAlertGrouper(mock_ai, mock_console)
        alert = sample_alerts[0]

        # Test nested field access
        assert grouper._get_field_value(alert, "labels.service") == "api"
        assert grouper._get_field_value(alert, "labels.namespace") == "production"
        assert (
            grouper._get_field_value(alert, "annotations.description")
            == "Memory usage is above 80%"
        )

        # Test non-existent field
        assert grouper._get_field_value(alert, "labels.nonexistent") is None
        assert grouper._get_field_value(alert, "nonexistent.field") is None

    @patch(
        "holmes.core.alert_grouping.SmartAlertGrouper._extract_rca_from_investigation"
    )
    @patch("holmes.core.alert_grouping.SmartAlertGrouper._check_root_cause_match")
    def test_process_single_alert_new_group(
        self, mock_check_match, mock_extract_rca, mock_ai, mock_console, sample_alerts
    ):
        """Test processing an alert that creates a new group"""
        grouper = SmartAlertGrouper(mock_ai, mock_console)

        # Mock investigation result
        mock_investigation = Mock()
        mock_investigation.analysis = "Memory exhaustion in API service"
        mock_ai.investigate.return_value = mock_investigation

        # Mock RCA extraction
        mock_extract_rca.return_value = {
            "root_cause": "Memory leak in API service",
            "evidence": ["High memory usage", "OOM kills"],
            "affected_components": ["api"],
            "category": "application",
        }

        # No existing groups match
        mock_check_match.return_value = False

        # Process alert
        group = grouper.process_single_alert(sample_alerts[0])

        assert group is not None
        assert group.root_cause == "Memory leak in API service"
        assert len(group.alerts) == 1
        assert group.alerts[0] == sample_alerts[0]
        assert len(grouper.groups) == 1

    @patch("holmes.core.alert_grouping.SmartAlertGrouper._verify_rule_match")
    def test_process_with_rule_verification(
        self, mock_verify, mock_ai, mock_console, sample_alerts
    ):
        """Test processing with rule verification"""
        grouper = SmartAlertGrouper(mock_ai, mock_console, verify_first_n=5)

        # Create a group and rule
        group = AlertGroup(
            id="group-1",
            root_cause="Memory exhaustion",
            alerts=[],
            category="application",
        )
        grouper.groups.append(group)

        rule = Rule(
            group_id="group-1",
            conditions=[
                Condition(field="labels.service", operator="equals", value="api")
            ],
            explanation="API memory issues",
            times_used=2,  # Less than verify_first_n
        )
        grouper.rules.append(rule)

        # Mock verification passes
        mock_verify.return_value = {
            "match_confirmed": True,
            "reason": "Alert matches pattern",
        }

        # Process alert
        result_group = grouper.process_single_alert(sample_alerts[0])

        # Should use the rule after verification
        assert result_group == group
        assert len(group.alerts) == 1
        assert rule.times_used == 3
        mock_verify.assert_called_once()

    def test_get_summary(self, mock_ai, mock_console, sample_alerts):
        """Test summary generation"""
        grouper = SmartAlertGrouper(mock_ai, mock_console)

        # Create some groups
        group1 = AlertGroup(
            id="group-1",
            root_cause="Memory exhaustion in API",
            alerts=sample_alerts[:2],
            category="application",
            has_rule=True,
        )
        group2 = AlertGroup(
            id="group-2",
            root_cause="Database connection issues",
            alerts=[sample_alerts[2]],
            category="database",
            has_rule=False,
        )
        grouper.groups = [group1, group2]
        grouper.rules = [Mock()]  # One rule

        summary = grouper.get_summary()

        assert "Total alerts: 3" in summary
        assert "Groups created: 2" in summary
        assert "Rules generated: 1" in summary
        assert "Memory exhaustion in API" in summary
        assert "Database connection issues" in summary
        assert "✓ Rule generated" in summary
