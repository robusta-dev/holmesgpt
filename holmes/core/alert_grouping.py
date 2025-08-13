"""
Alert grouping system that uses RCA and LLM-generated rules for intelligent alert correlation.
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic.json import pydantic_encoder

from holmes.core.issue import Issue


class Condition(BaseModel):
    """A single condition for matching alerts"""

    field: str
    operator: str  # equals, contains, in, regex, exists
    value: Any


class Rule(BaseModel):
    """A rule for matching alerts to groups"""

    group_id: str
    conditions: List[Condition]
    explanation: str
    times_used: int = 0
    needs_regeneration: bool = False


class AlertGroup(BaseModel):
    """A group of related alerts with common root cause"""

    id: str
    issue_title: str  # Concise title describing the issue
    root_cause: str  # Detailed root cause analysis
    alerts: List[Issue] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    category: str = "unknown"
    has_rule: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True


class RCAResult(BaseModel):
    """Structured root cause analysis result"""

    issue_title: str  # Concise title describing the issue
    root_cause: str  # Detailed root cause explanation
    evidence: List[str]
    affected_components: List[str]
    remediation: Optional[str] = None
    category: str


class SmartAlertGrouper:
    """
    Groups alerts by root cause using RCA and learned rules.

    Flow:
    1. Try matching with existing rules (verify first N matches)
    2. If no rule matches, run RCA
    3. Check if RCA matches existing groups
    4. Create new group if needed
    5. Generate rules when patterns emerge
    """

    def __init__(self, ai, console, verify_first_n: int = 5):
        self.ai = ai
        self.console = console
        self.groups: List[AlertGroup] = []
        self.rules: List[Rule] = []
        self.verify_first_n = verify_first_n

    def process_alerts(
        self, alerts: List[Issue], show_progress: bool = True
    ) -> List[AlertGroup]:
        """
        Process a list of alerts and group them by root cause.

        Args:
            alerts: List of alerts to process
            show_progress: Whether to show progress in console

        Returns:
            List of alert groups
        """
        if show_progress:
            self.console.print(
                f"\n[bold yellow]Grouping {len(alerts)} alerts by root cause...[/bold yellow]"
            )

        for i, alert in enumerate(alerts):
            if show_progress:
                self.console.print(f"[{i+1}/{len(alerts)}] Processing {alert.name}...")

            group = self.process_single_alert(alert)

            if show_progress and group:
                self.console.print(f"  → Grouped into: {group.issue_title}")

        return self.groups

    def process_single_alert(self, alert: Issue) -> Optional[AlertGroup]:
        """Process a single alert and add it to appropriate group"""

        # 1. Try rules first
        for rule in self.rules:
            if self._matches_rule(alert, rule):
                if rule.times_used < self.verify_first_n:
                    # Verify with LLM
                    verification = self._verify_rule_match(alert, rule)

                    if verification.get("match_confirmed", False):
                        rule.times_used += 1
                        group = self._get_group(rule.group_id)
                        if group:
                            group.alerts.append(alert)
                            logging.info(
                                f"✓ Rule match verified: {alert.name} → {group.id}"
                            )
                            return group
                    else:
                        logging.info(
                            f"✗ Rule match failed verification for {alert.name}"
                        )
                        if verification.get("suggested_adjustment"):
                            self._adjust_rule(
                                rule, verification["suggested_adjustment"]
                            )
                        # Continue to RCA since rule didn't match
                else:
                    # Rule is trusted
                    rule.times_used += 1
                    group = self._get_group(rule.group_id)
                    if group:
                        group.alerts.append(alert)
                        logging.info(
                            f"Alert {alert.name} → Group {group.id} (trusted rule)"
                        )
                        return group

        # 2. No rule matched - run RCA
        self.console.print("  Running root cause analysis...")
        investigation = self.ai.investigate(
            issue=alert,
            prompt="builtin://generic_investigation.jinja2",
            console=self.console,
            instructions=None,
            post_processing_prompt=None,
        )

        rca = self._extract_rca_from_investigation(investigation, alert)

        # 3. Check if this root cause matches existing groups
        for group in self.groups:
            if self._check_root_cause_match(rca, group):
                group.alerts.append(alert)
                logging.info(f"Alert {alert.name} → Group {group.id} (same root cause)")

                # Maybe generate a rule
                if len(group.alerts) >= 3 and not group.has_rule:
                    generated_rule = self._generate_rule(group)
                    if generated_rule is not None:
                        self.rules.append(generated_rule)
                        group.has_rule = True
                        logging.info(f"Generated rule for group {group.id}")

                return group

        # 4. New root cause - create new group
        group = AlertGroup(
            id=f"group-{uuid.uuid4().hex[:8]}",
            issue_title=rca.get("issue_title", "Unknown Issue"),
            root_cause=rca["root_cause"],
            alerts=[alert],
            evidence=rca.get("evidence", []),
            affected_components=rca.get("affected_components", []),
            category=rca.get("category", "unknown"),
        )
        self.groups.append(group)
        logging.info(f"Alert {alert.name} → New Group {group.id}")
        return group

    def _matches_rule(self, alert: Issue, rule: Rule) -> bool:
        """Check if an alert matches a rule's conditions"""
        for condition in rule.conditions:
            if not self._check_condition(alert, condition):
                return False
        return True

    def _check_condition(self, alert: Issue, condition: Condition) -> bool:
        """Check a single condition against an alert"""
        value = self._get_field_value(alert, condition.field)

        if condition.operator == "equals":
            return value == condition.value
        elif condition.operator == "contains":
            return condition.value in str(value)
        elif condition.operator == "in":
            return value in condition.value
        elif condition.operator == "regex":
            import re

            return bool(re.search(condition.value, str(value)))
        elif condition.operator == "exists":
            return value is not None

        return False

    def _get_field_value(self, alert: Issue, field_path: str) -> Any:
        """Get a field value from an alert using dot notation"""
        parts = field_path.split(".")
        value = alert.raw

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value

    def _get_group(self, group_id: str) -> Optional[AlertGroup]:
        """Get a group by ID"""
        for group in self.groups:
            if group.id == group_id:
                return group
        return None

    def _verify_rule_match(self, alert: Issue, rule: Rule) -> Dict[str, Any]:
        """Verify if an alert truly matches a rule using LLM"""
        group = self._get_group(rule.group_id)
        if not group:
            return {"match_confirmed": False, "reason": "Group not found"}

        prompt = f"""
Verify if this alert actually matches the rule's intended pattern.

Rule explanation: {rule.explanation}
Rule conditions: {json.dumps([c.dict() for c in rule.conditions], indent=2)}

Alert: {json.dumps(alert.raw, indent=2, default=pydantic_encoder)}

Group this rule maps to:
Root cause: {group.root_cause}

Check if this alert truly belongs to this group.
If not, suggest how to adjust the rule.
"""

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "rule_verification",
                "schema": {
                    "type": "object",
                    "properties": {
                        "match_confirmed": {"type": "boolean"},
                        "reason": {"type": "string"},
                        "suggested_adjustment": {
                            "type": ["object", "null"],
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "add_condition",
                                        "remove_condition",
                                        "modify_condition",
                                        "replace_rule",
                                    ],
                                },
                                "details": {"type": "object"},
                                "adjustment_reason": {"type": "string"},
                            },
                        },
                    },
                    "required": ["match_confirmed", "reason"],
                },
            },
        }

        messages = [
            {
                "role": "system",
                "content": "You are an expert at analyzing alerts and their patterns.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.ai.llm.completion(messages, response_format=response_format)
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logging.error(f"Error verifying rule match: {e}")
            return {"match_confirmed": False, "reason": str(e)}

    def _adjust_rule(self, rule: Rule, adjustment: Dict[str, Any]):
        """Apply LLM-suggested adjustment to a rule"""
        action = adjustment.get("action")
        details = adjustment.get("details", {})

        if action == "add_condition":
            new_condition = Condition(**details.get("new_condition", {}))
            rule.conditions.append(new_condition)

        elif action == "remove_condition":
            idx = details.get("condition_index", -1)
            if 0 <= idx < len(rule.conditions):
                rule.conditions.pop(idx)

        elif action == "modify_condition":
            idx = details.get("condition_index", -1)
            if 0 <= idx < len(rule.conditions):
                new_condition = Condition(**details.get("new_condition", {}))
                rule.conditions[idx] = new_condition

        elif action == "replace_rule":
            rule.needs_regeneration = True

        # Reset verification counter since rule changed
        rule.times_used = 0

        logging.info(
            f"Rule adjusted: {adjustment.get('adjustment_reason', 'No reason provided')}"
        )

    def _extract_rca_from_investigation(
        self, investigation, alert: Issue
    ) -> Dict[str, Any]:
        """Extract structured RCA from investigation result"""
        prompt = f"""
Based on the investigation, provide the root cause analysis.

Investigation results:
{investigation.result}

Alert details:
{json.dumps(alert.raw, indent=2, default=pydantic_encoder)}

Provide:
1. issue_title: A concise, descriptive title for the issue (10-15 words max, like "Database Connection Pool Exhaustion" or "Node Memory Pressure Causing Pod Evictions")
2. root_cause: A detailed explanation of the root cause (2-3 sentences)
"""

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "rca_result",
                "schema": {
                    "type": "object",
                    "properties": {
                        "issue_title": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "affected_components": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "remediation": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": [
                                "infrastructure",
                                "application",
                                "database",
                                "network",
                                "configuration",
                                "capacity",
                                "unknown",
                            ],
                        },
                    },
                    "required": [
                        "issue_title",
                        "root_cause",
                        "evidence",
                        "affected_components",
                        "category",
                    ],
                },
            },
        }

        messages = [
            {
                "role": "system",
                "content": "Extract structured root cause analysis from the investigation.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.ai.llm.completion(messages, response_format=response_format)
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logging.error(f"Error extracting RCA: {e}")
            # Fallback to basic extraction
            return {
                "issue_title": alert.name if alert.name else "Unknown Issue",
                "root_cause": investigation.result[:200]
                if investigation.result
                else "Unknown",
                "evidence": [],
                "affected_components": [],
                "category": "unknown",
            }

    def _check_root_cause_match(self, rca: Dict[str, Any], group: AlertGroup) -> bool:
        """Check if an RCA matches an existing group's root cause"""
        prompt = f"""
Compare this alert's root cause with an existing group.

New alert RCA:
{json.dumps(rca, indent=2, default=pydantic_encoder)}

Existing group:
Root cause: {group.root_cause}
Evidence: {json.dumps(group.evidence, indent=2, default=pydantic_encoder)}
Affected components: {json.dumps(group.affected_components, indent=2, default=pydantic_encoder)}

Determine if they have the same root cause.
"""

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "root_cause_match",
                "schema": {
                    "type": "object",
                    "properties": {
                        "same_root_cause": {"type": "boolean"},
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "reasoning": {"type": "string"},
                    },
                    "required": ["same_root_cause", "confidence", "reasoning"],
                },
            },
        }

        messages = [
            {
                "role": "system",
                "content": "You are an expert at identifying common root causes in system failures.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.ai.llm.completion(messages, response_format=response_format)
            result = json.loads(response.choices[0].message.content)
            return result.get("same_root_cause", False)
        except Exception as e:
            logging.error(f"Error checking root cause match: {e}")
            return False

    def _generate_rule(self, group: AlertGroup) -> Optional[Rule]:
        """Generate a rule for matching future alerts to this group"""
        # Extract alert details for rule generation
        alert_details = []
        for alert in group.alerts[:5]:  # Use up to 5 examples
            alert_details.append(
                {
                    "name": alert.name,
                    "labels": alert.raw.get("labels", {}) if alert.raw else {},
                    "annotations": alert.raw.get("annotations", {})
                    if alert.raw
                    else {},
                }
            )

        prompt = f"""
Generate a rule to match future alerts with this root cause.

Group root cause: {group.root_cause}
Category: {group.category}
Alerts in group: {json.dumps(alert_details, indent=2, default=pydantic_encoder)}

Create conditions that would match these alerts.
Only generate a rule if there's a clear pattern.
"""

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "grouping_rule",
                "schema": {
                    "type": "object",
                    "properties": {
                        "rule_generated": {"type": "boolean"},
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field": {"type": "string"},
                                    "operator": {
                                        "type": "string",
                                        "enum": [
                                            "equals",
                                            "contains",
                                            "in",
                                            "regex",
                                            "exists",
                                        ],
                                    },
                                    "value": {},
                                },
                                "required": ["field", "operator", "value"],
                            },
                        },
                        "explanation": {"type": "string"},
                        "expected_precision": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": ["rule_generated", "explanation"],
                },
            },
        }

        messages = [
            {
                "role": "system",
                "content": "You are an expert at identifying patterns in alerts.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.ai.llm.completion(messages, response_format=response_format)
            result = json.loads(response.choices[0].message.content)

            if result.get("rule_generated") and result.get("conditions"):
                return Rule(
                    group_id=group.id,
                    conditions=[Condition(**c) for c in result["conditions"]],
                    explanation=result["explanation"],
                )
        except Exception as e:
            logging.error(f"Error generating rule: {e}")

        return None

    def get_summary(self) -> str:
        """Get a summary of the grouping results"""
        if not self.groups:
            return "No alert groups created."

        summary = []
        summary.append("\n[bold]Alert Grouping Summary:[/bold]")
        summary.append(f"Total alerts: {sum(len(g.alerts) for g in self.groups)}")
        summary.append(f"Groups created: {len(self.groups)}")
        summary.append(f"Rules generated: {len(self.rules)}")

        summary.append("\n[bold]Groups:[/bold]")
        for group in self.groups:
            summary.append(f"\n[yellow]Group {group.id}:[/yellow]")
            summary.append(f"  Issue: {group.issue_title}")
            summary.append(f"  Root Cause: {group.root_cause}")
            summary.append(f"  Category: {group.category}")
            summary.append(f"  Alerts ({len(group.alerts)}):")
            for alert in group.alerts[:5]:  # Show first 5
                summary.append(f"    - {alert.name}")
            if len(group.alerts) > 5:
                summary.append(f"    ... and {len(group.alerts) - 5} more")
            if group.has_rule:
                summary.append("  [green]✓ Rule generated[/green]")

        return "\n".join(summary)
