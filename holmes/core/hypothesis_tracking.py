import logging
from typing import List, Optional, Dict, TypedDict
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from holmes.core.tools import (
    Tool,
    ToolParameter,
    StructuredToolResult,
    ToolResultStatus,
)


class HypothesisStatus(str, Enum):
    PENDING = "pending"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"


# TODO: Implement hypothesis relationships in future iteration
# This would allow modeling relationships like:
# - "Missing index" is a SUBPROBLEM_OF "Database performance issues"
# - "Memory leak" CONTRADICTS "Configuration issue"
# - "High CPU" CAUSES "Slow response times"
#
# Implementation approach:
# 1. Add relationships field to Hypothesis model
# 2. Update the LLM prompt to understand and use relationships
# 3. Add visualization/graph building for relationship networks
# 4. Consider adding relationship validation (no cycles, valid targets)
#
# class HypothesisRelation(str, Enum):
#     CAUSES = "causes"
#     CAUSED_BY = "caused_by"
#     CONTRIBUTES_TO = "contributes_to"
#     CONTRADICTS = "contradicts"
#     RELATED_TO = "related_to"
#     SUBPROBLEM_OF = "subproblem_of"
#     ALTERNATIVE_TO = "alternative_to"
#
# class HypothesisRelationship(BaseModel):
#     relation_type: HypothesisRelation
#     target_hypothesis_id: str
#     notes: Optional[str] = None


class Hypothesis(BaseModel):
    id: str
    description: str
    status: HypothesisStatus = HypothesisStatus.PENDING
    evidence_for: List[str] = Field(default_factory=list)
    evidence_against: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    tool_calls_made: List[str] = Field(default_factory=list)
    # TODO: Add relationships field when implementing relationship support
    # relationships: List[HypothesisRelationship] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class HypothesisInfo(TypedDict):
    hypothesis: Hypothesis
    is_new: bool
    status_changed: bool
    old_status: Optional[HypothesisStatus]


class UpdateHypotheses(Tool):
    """Tool for tracking and managing investigation hypotheses"""

    # Storage for current hypotheses - class variable shared across instances
    _hypotheses: List[Hypothesis] = []

    @classmethod
    def get_current_hypotheses_summary(cls) -> Optional[str]:
        """Get a summary of current hypotheses for context injection"""
        if not cls._hypotheses:
            return None

        summary_parts = ["Current Investigation Hypotheses:"]

        # Group by status
        status_groups: Dict[HypothesisStatus, List[Hypothesis]] = {
            HypothesisStatus.INVESTIGATING: [],
            HypothesisStatus.PENDING: [],
            HypothesisStatus.CONFIRMED: [],
            HypothesisStatus.REFUTED: [],
        }

        for h in cls._hypotheses:
            status_groups[h.status].append(h)

        # Format each group
        for status, hypotheses in status_groups.items():
            if hypotheses:
                summary_parts.append(f"\n{status.value.upper()}:")
                for h in hypotheses:
                    summary_parts.append(f"- {h.id}: {h.description}")
                    if h.evidence_for and status == HypothesisStatus.INVESTIGATING:
                        summary_parts.append(f"  Evidence: {h.evidence_for[-1]}")

        # Add statistics
        investigating = len(status_groups[HypothesisStatus.INVESTIGATING])
        confirmed = len(status_groups[HypothesisStatus.CONFIRMED])
        total = len(cls._hypotheses)
        summary_parts.append(
            f"\nProgress: {investigating} investigating, {confirmed} confirmed, {total} total"
        )

        return "\n".join(summary_parts)

    def __init__(self):
        parameters = {
            "hypotheses": ToolParameter(
                description="List of hypotheses with their current status and evidence",
                type="array[object]",  # Array of hypothesis objects
                required=True,
            ),
            "investigation_summary": ToolParameter(
                description="Optional summary of the current investigation state",
                type="string",
                required=False,
            ),
        }
        super().__init__(
            name="update_hypotheses",
            description="Update the current investigation hypotheses with evidence and status changes. Use this to track root cause analysis progress.",
            parameters=parameters,
        )

    def _invoke(self, params: dict) -> StructuredToolResult:
        try:
            hypotheses_data = params.get("hypotheses", [])
            summary = params.get("investigation_summary", "")

            # Create a map of existing hypotheses to preserve history
            existing_map = {h.id: h for h in self._hypotheses}

            # Update hypotheses - never remove, only update
            updated_hypotheses = []
            for h_data in hypotheses_data:
                hypothesis = Hypothesis(**h_data)
                hypothesis.updated_at = datetime.now()

                # Preserve creation time if updating existing
                if hypothesis.id in existing_map:
                    hypothesis.created_at = existing_map[hypothesis.id].created_at

                updated_hypotheses.append(hypothesis)

            # Print user-friendly output
            self._print_hypothesis_updates(existing_map, updated_hypotheses, summary)

            # Merge: keep all hypotheses, update ones that were provided
            all_hypothesis_ids = set(existing_map.keys()) | set(
                h.id for h in updated_hypotheses
            )
            self._hypotheses = []
            for h_id in all_hypothesis_ids:
                if h_id in [h.id for h in updated_hypotheses]:
                    # Use the updated version
                    self._hypotheses.append(
                        next(h for h in updated_hypotheses if h.id == h_id)
                    )
                else:
                    # Keep the existing one unchanged
                    self._hypotheses.append(existing_map[h_id])

            # Format response
            response_data = {
                "hypotheses": [h.model_dump() for h in self._hypotheses],
                "summary": summary,
                "active_investigations": len(
                    [
                        h
                        for h in self._hypotheses
                        if h.status == HypothesisStatus.INVESTIGATING
                    ]
                ),
                "confirmed_hypotheses": len(
                    [
                        h
                        for h in self._hypotheses
                        if h.status == HypothesisStatus.CONFIRMED
                    ]
                ),
                "refuted_hypotheses": len(
                    [
                        h
                        for h in self._hypotheses
                        if h.status == HypothesisStatus.REFUTED
                    ]
                ),
                "total_hypotheses": len(self._hypotheses),
            }

            return StructuredToolResult(
                status=ToolResultStatus.SUCCESS, data=response_data
            )

        except Exception as e:
            return StructuredToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to update hypotheses: {str(e)}",
            )

    def _print_hypothesis_updates(
        self,
        existing_map: Dict[str, Hypothesis],
        updated_hypotheses: List[Hypothesis],
        summary: str,
    ):
        """Print user-friendly output for hypothesis updates"""

        # Print header
        if not existing_map:
            logging.info("\n[bold green]⚡ Creating Initial Hypotheses[/bold green]")
        else:
            logging.info("\n[bold blue]🔄 Updating Hypotheses[/bold blue]")

        # Group hypotheses by status for cleaner output
        status_groups: Dict[HypothesisStatus, List[HypothesisInfo]] = {
            HypothesisStatus.INVESTIGATING: [],
            HypothesisStatus.PENDING: [],
            HypothesisStatus.CONFIRMED: [],
            HypothesisStatus.REFUTED: [],
        }

        # Process each hypothesis
        for h in updated_hypotheses:
            existing = existing_map.get(h.id)
            status_changed = bool(existing and existing.status != h.status)
            is_new = h.id not in existing_map

            # Build hypothesis info
            h_info: HypothesisInfo = {
                "hypothesis": h,
                "is_new": is_new,
                "status_changed": status_changed,
                "old_status": existing.status if existing else None,
            }
            status_groups[h.status].append(h_info)

        # Print hypotheses by status
        status_icons = {
            HypothesisStatus.INVESTIGATING: "🔍",
            HypothesisStatus.PENDING: "💭",
            HypothesisStatus.CONFIRMED: "✅",
            HypothesisStatus.REFUTED: "❌",
        }

        status_colors = {
            HypothesisStatus.INVESTIGATING: "yellow",
            HypothesisStatus.PENDING: "white",
            HypothesisStatus.CONFIRMED: "green",
            HypothesisStatus.REFUTED: "red",
        }

        for status, hypotheses in status_groups.items():
            if hypotheses:
                color = status_colors[status]
                icon = status_icons[status]
                logging.info(f"\n  [{color}]{icon} {status.value.upper()}[/{color}]")

                for h_info in hypotheses:
                    h = h_info["hypothesis"]
                    prefix = "  ⎿ "

                    # Format the hypothesis line
                    if h_info["is_new"]:
                        logging.info(
                            f"{prefix}[bold]{h.id}[/bold]: {h.description} [dim](new)[/dim]"
                        )
                    elif h_info["status_changed"]:
                        old_status = h_info["old_status"]
                        old_status_value = old_status.value if old_status else "unknown"
                        logging.info(
                            f"{prefix}[bold]{h.id}[/bold]: {h.description} [dim](was {old_status_value})[/dim]"
                        )
                    else:
                        logging.info(f"{prefix}[bold]{h.id}[/bold]: {h.description}")

                    # Show key evidence if status is not pending
                    if h.status != HypothesisStatus.PENDING:
                        if h.evidence_for and h.status in [
                            HypothesisStatus.INVESTIGATING,
                            HypothesisStatus.CONFIRMED,
                        ]:
                            logging.info(
                                f"     [green]Evidence for:[/green] {h.evidence_for[-1]}"
                            )
                        if h.evidence_against and h.status in [
                            HypothesisStatus.INVESTIGATING,
                            HypothesisStatus.REFUTED,
                        ]:
                            logging.info(
                                f"     [red]Evidence against:[/red] {h.evidence_against[-1]}"
                            )

        # Print summary if provided
        if summary:
            logging.info(f"\n[bold]📊 Summary:[/bold] {summary}")

        # Print statistics (count from the merged state)
        investigating = len(
            [h for h in self._hypotheses if h.status == HypothesisStatus.INVESTIGATING]
        )
        confirmed = len(
            [h for h in self._hypotheses if h.status == HypothesisStatus.CONFIRMED]
        )
        refuted = len(
            [h for h in self._hypotheses if h.status == HypothesisStatus.REFUTED]
        )
        total = len(self._hypotheses)

        logging.info(
            f"\n[dim]Total: {total} hypotheses | "
            f"Investigating: {investigating} | "
            f"Confirmed: {confirmed} | "
            f"Refuted: {refuted}[/dim]\n"
        )

    def get_parameterized_one_liner(self, params: dict) -> str:
        num_hypotheses = len(params.get("hypotheses", []))
        return f"Updating {num_hypotheses} investigation hypotheses"

    def get_context_reminder(self) -> Optional[str]:
        """Provide current hypothesis state as context for next tool calls"""
        if not self._hypotheses:
            return None

        reminder_parts = []
        reminder_parts.append("Current Investigation Hypotheses:")

        # Group by status for cleaner display
        status_groups: Dict[HypothesisStatus, List[Hypothesis]] = {
            HypothesisStatus.INVESTIGATING: [],
            HypothesisStatus.PENDING: [],
            HypothesisStatus.CONFIRMED: [],
            HypothesisStatus.REFUTED: [],
        }

        for h in self._hypotheses:
            status_groups[h.status].append(h)

        # Show investigating hypotheses first (most relevant)
        if status_groups[HypothesisStatus.INVESTIGATING]:
            reminder_parts.append("\nACTIVELY INVESTIGATING:")
            for h in status_groups[HypothesisStatus.INVESTIGATING]:
                reminder_parts.append(f"• {h.id}: {h.description}")
                if h.next_steps:
                    reminder_parts.append(f"  Next: {h.next_steps[0]}")

        # Show pending hypotheses
        if status_groups[HypothesisStatus.PENDING]:
            reminder_parts.append("\nPENDING INVESTIGATION:")
            for h in status_groups[HypothesisStatus.PENDING]:
                reminder_parts.append(f"• {h.id}: {h.description}")

        # Summary statistics
        investigating = len(status_groups[HypothesisStatus.INVESTIGATING])
        confirmed = len(status_groups[HypothesisStatus.CONFIRMED])
        total = len(self._hypotheses)

        reminder_parts.append(
            f"\nStatus: {investigating} investigating, {confirmed} confirmed, {total} total"
        )

        # Strong reminder based on state
        if confirmed == 0 and total > 0:
            reminder_parts.append(
                "\n⚠️  NO HYPOTHESES CONFIRMED YET - Update with root cause before concluding!"
            )
        else:
            reminder_parts.append(
                "\nRemember to update hypotheses with evidence after each tool call!"
            )

        return "\n".join(reminder_parts)
