import os
import logging
from typing import Any, Optional, Dict, List, Tuple
from holmes.core.tools import (
    CallablePrerequisite,
    Tool,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from pydantic import BaseModel
from holmes.core.tools import StructuredToolResult, StructuredToolResultStatus
from holmes.plugins.toolsets.utils import toolset_name_for_one_liner
from holmes.plugins.toolsets.newrelic.new_relic_api import NewRelicAPI
import yaml
import json
import uuid
import math
from datetime import datetime, timezone


class ExecuteNRQLQuery(Tool):
    def __init__(self, toolset: "NewRelicToolset"):
        super().__init__(
            name="newrelic_execute_nrql_query",
            description="Get Traces, APM, Spans, Logs and more by executing a NRQL query in New Relic. "
            "Returns the result of the NRQL function. "
            "⚠️ CRITICAL: NRQL silently returns empty results for invalid queries instead of errors. "
            "If you get empty results, your query likely has issues such as: "
            "1) Wrong attribute names (use SELECT keyset() first to verify), "
            "2) Type mismatches (string vs numeric fields), "
            "3) Wrong event type. "
            "Always verify attribute names and types before querying.",
            parameters={
                "query": ToolParameter(
                    description="""The NRQL query string to execute.

MANDATORY: Before querying any event type, ALWAYS run `SELECT keyset() FROM <EventType> SINCE <timeframe>` to discover available attributes. Never use attributes without confirming they exist first. Make sure to remember which fields are stringKeys, numericKeys or booleanKeys as this will be important in subsequent queries.

Example: Before querying Transactions, run: `SELECT keyset() FROM Transaction SINCE 24 hours ago`

### ⚠️ Critical Rule: NRQL `FACET` Usa ge

When using **FACET** in NRQL:
- Any **non-constant value** in the `SELECT` clause **must be aggregated**.
- The attribute you **FACET** on must **not appear in `SELECT`** unless it’s wrapped in an aggregation.

#### ✅ Correct
```nrql
-- Aggregated metric + facet
SELECT count(*) FROM Transaction FACET transactionType

-- Multiple aggregations with facet
SELECT count(*), average(duration) FROM Transaction FACET transactionType
```

#### ❌ Incorrect
```nrql
-- Not allowed: raw attribute in SELECT
SELECT count(*), transactionType FROM Transaction FACET transactionType
```
""",
                    type="string",
                    required=True,
                ),
                "description": ToolParameter(
                    description="A breif 6 word human understandable description of the query you are running.",
                    type="string",
                    required=True,
                ),
                "query_type": ToolParameter(
                    description="Either 'Metrics', 'Logs', 'Traces', 'Discover Attributes' or 'Other'.",
                    type="string",
                    required=True,
                ),
            },
        )
        self._toolset = toolset

    def format_metrics(
        self,
        records: List[Dict[str, Any]],
        params: Optional[Dict[str, Any]] = None,
        begin_key: str = "beginTimeSeconds",
        end_key: str = "endTimeSeconds",
        facet_key: str = "facet",
    ) -> Dict[str, Any]:
        """
        Transform New Relic NerdGraph `nrql.results` (flattened) into a Prometheus-like HTTP API response:
        {
            "status": "success",
            "error_message": null,
            "random_key": "<hex>",
            "tool_name": <tool name>,
            "description": <string>,
            "query": <nrql>,
            "start": "RFC3339",
            "end": "RFC3339",
            "step": <seconds>,
            "output_type": <string>,
            "data": {
            "resultType": "matrix",
            "result": [
                {"metric": { "__name__": "<metric>", <labels...> }, "values": [[<ts>, "<val>"], ...]},
                ...
            ]
            }
        }

        Notes:
        - Uses endTimeSeconds as the sample timestamp (common convention for bucketed series).
        - Maps None to "NaN" (Prometheus JSON uses strings for values; "NaN" is conventional).
        - Supports multiple metrics in the same result set (e.g., average.duration, count).
        """

        params = params or {}

        def rfc3339(ts: Optional[int]) -> str:
            if ts is None:
                return ""
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        def to_prom_value(v: Any) -> str:
            if v is None:
                return "NaN"
            if isinstance(v, bool):
                return "1" if v else "0"
            if isinstance(v, (int, float)):
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    return "NaN"
                return str(v)
            # try numeric-ish strings
            try:
                fv = float(v)
                if math.isnan(fv) or math.isinf(fv):
                    return "NaN"
                return str(fv)
            except Exception:
                return "NaN"

        if not records:
            return {
                "status": "success",
                "error_message": None,
                "random_key": uuid.uuid4().hex,
                "tool_name": self.name,
                "description": params.get("description", ""),
                "query": params.get("query", ""),
                "start": "",
                "end": "",
                "step": 60,
                "output_type": params.get("output_type", "Plain"),
                "data": {"resultType": "matrix", "result": []},
            }

        # All keys seen
        all_keys = set().union(*(r.keys() for r in records))

        # Reserved/time keys
        reserved = {begin_key, end_key, facet_key, "timestamp"}

        # Heuristic: metric keys are numeric/None and not time-like;
        # prefer keys with an aggregator dot (e.g., "average.duration")
        known_metric_singletons = {"count", "rate", "apdex"}
        metric_keys = set()
        for k in all_keys - reserved:
            if "." in k or k in known_metric_singletons:
                metric_keys.add(k)

        # Fallback: anything numeric/None across the set
        if not metric_keys:
            for k in all_keys - reserved:
                if any(
                    isinstance(r.get(k), (int, float)) or r.get(k) is None
                    for r in records
                ):
                    metric_keys.add(k)

        # Label keys: what's left (including facet, podName, namespaceName, etc.)
        label_keys = sorted((all_keys - metric_keys))

        # Determine global start/end and bucket step
        begins = [
            r.get(begin_key)
            for r in records
            if isinstance(r.get(begin_key), (int, float))
        ]
        ends = [
            r.get(end_key) for r in records if isinstance(r.get(end_key), (int, float))
        ]
        start_ts = min(begins) if begins else (min(ends) if ends else None)  # type: ignore
        end_ts = max(ends) if ends else (max(begins) if begins else None)  # type: ignore

        # Step: use the most common (end - begin) delta if available; else infer from consecutive buckets; else 60
        deltas = [
            int(r[end_key] - r[begin_key])
            for r in records
            if isinstance(r.get(end_key), (int, float))
            and isinstance(r.get(begin_key), (int, float))
        ]
        if deltas:
            # pick mode
            step = max(set(deltas), key=deltas.count)
        else:
            # Try to infer from sorted end timestamps
            sorted_ends = sorted([int(e) for e in ends]) if ends else []  # type: ignore
            consec = [b - a for a, b in zip(sorted_ends, sorted_ends[1:])]
            step = max(set(consec), key=consec.count) if consec else 60

        # Group records by labels (excluding metric keys)
        def label_tuple(rec: Dict[str, Any]) -> Tuple[Tuple[str, Any], ...]:
            # Only include known label keys present in this record
            items = []
            for k in label_keys:
                if k in reserved:
                    continue
                if k in rec:
                    items.append((k, rec.get(k)))
            return tuple(sorted(items))

        groups: Dict[Tuple[Tuple[str, Any], ...], List[Dict[str, Any]]] = {}
        for rec in records:
            lt = label_tuple(rec)
            groups.setdefault(lt, []).append(rec)

        # Build Prometheus-like series
        prom_series: List[Dict[str, Any]] = []
        for lt, recs in groups.items():
            # Compute the label dict for this group
            labels = {k: v for (k, v) in lt}

            # Sort buckets by end time (fallback to begin time)
            recs_sorted = sorted(
                recs,
                key=lambda r: (
                    r.get(end_key) is None,
                    r.get(end_key),
                    r.get(begin_key),
                ),
            )

            # For each metric key, produce a series
            for mkey in sorted(metric_keys):
                metric = {"__name__": mkey}
                metric.update(labels)

                values: List[List[Any]] = []
                for r in recs_sorted:
                    # Pick timestamp: prefer end, else begin, else skip
                    ts = r.get(end_key) or r.get(begin_key)
                    if not isinstance(ts, (int, float)):
                        continue
                    v = to_prom_value(r.get(mkey))
                    values.append([int(ts), v])

                # Only append if we have at least one point
                if values:
                    prom_series.append({"metric": metric, "values": values})

        response_data = {
            "status": "success",
            "error_message": None,
            "random_key": uuid.uuid4().hex,
            "tool_name": self.name,
            "description": params.get("description", ""),
            "query": params.get("query", ""),
            "start": rfc3339(int(start_ts)) if start_ts is not None else "",
            "end": rfc3339(int(end_ts)) if end_ts is not None else "",
            "step": int(step),
            "output_type": params.get("output_type", "Plain"),
            "data": {"resultType": "matrix", "result": prom_series},
        }
        return response_data

    # 2) Update _invoke to use the Prometheus-style formatter for metrics / TIMESERIES
    #    (keep your existing logs path as-is)
    def _invoke(
        self, params: dict, user_approved: bool = False
    ) -> StructuredToolResult:
        if not self._toolset.nr_api_key or not self._toolset.nr_account_id:
            raise ValueError("NewRelic API key or account ID is not configured")

        api = NewRelicAPI(
            api_key=self._toolset.nr_api_key,
            account_id=self._toolset.nr_account_id,
            is_eu_datacenter=self._toolset.is_eu_datacenter,
        )

        query = params["query"]
        result: List[Dict[str, Any]] = api.execute_nrql_query(query)

        qtype = params.get("query_type", "").lower()
        if qtype == "logs":
            formatted = self.format_logs(result)
            # For logs we keep your existing YAML output (unchanged)
            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=yaml.dump(formatted, default_flow_style=False),
                params=params,
            )

        # Treat explicit "Metrics" OR any query containing TIMESERIES as metrics
        if qtype == "metrics" or "timeseries" in query.lower():
            enriched_params = dict(params)
            enriched_params["query"] = query
            formatted = self.format_metrics(result, params=enriched_params)
            return StructuredToolResult(
                status=StructuredToolResultStatus.SUCCESS,
                data=json.dumps(formatted, indent=2),
                params=params,
            )

        return StructuredToolResult(
            status=StructuredToolResultStatus.SUCCESS,
            data=yaml.dump(result, default_flow_style=False),
            params=params,
        )

    def format_logs(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not records:
            return []

        def to_hashable(v: Any):
            if isinstance(v, (str, int, float, bool)) or v is None:
                return v
            # Fallback for unhashable types (lists/dicts/etc.)
            return repr(v)

        # Preserve key discovery order across all records
        all_keys_order: List[str] = []
        seen = set()
        for rec in records:
            for k in rec.keys():
                if k not in seen:
                    seen.add(k)
                    all_keys_order.append(k)

        # Common (duplicate) fields = keys present in every record with identical value
        common_fields: Dict[str, Any] = {}
        for k in all_keys_order:
            if k not in records[0]:
                continue
            ref = to_hashable(records[0][k])
            same = True
            for r in records[1:]:
                if k not in r or to_hashable(r[k]) != ref:
                    same = False
                    break
            if same:
                common_fields[k] = records[0][k]

        # Per-record unique fields: everything not lifted to common_fields
        data_entries: List[Dict[str, Any]] = []
        for r in records:
            entry: Dict[str, Any] = {}
            for k, v in r.items():
                if k not in common_fields:
                    entry[k] = v
            data_entries.append(entry)

        # Assemble final single group
        group_obj = dict(common_fields)
        # avoid clobbering if an input field is literally named "data"
        if "data" in group_obj:
            group_obj["_common.data"] = group_obj.pop("data")
        group_obj["data"] = data_entries

        return [group_obj]

    def get_parameterized_one_liner(self, params) -> str:
        description = params.get("description", "")
        return f"{toolset_name_for_one_liner(self._toolset.name)}: Execute NRQL ({description})"


class NewrelicConfig(BaseModel):
    nr_api_key: Optional[str] = None
    nr_account_id: Optional[str] = None
    is_eu_datacenter: Optional[bool] = False


class NewRelicToolset(Toolset):
    nr_api_key: Optional[str] = None
    nr_account_id: Optional[str] = None
    is_eu_datacenter: bool = False

    def __init__(self):
        super().__init__(
            name="newrelic",
            description="Toolset for interacting with New Relic to fetch logs, traces, and execute freeform NRQL queries",
            docs_url="https://holmesgpt.dev/data-sources/builtin-toolsets/newrelic/",
            icon_url="https://companieslogo.com/img/orig/NEWR-de5fcb2e.png?t=1720244493",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],  # type: ignore
            tools=[
                ExecuteNRQLQuery(self),
            ],
            experimental=True,
            tags=[ToolsetTag.CORE],
        )
        template_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "newrelic.jinja2")
        )
        self._load_llm_instructions(jinja_template=f"file://{template_file_path}")

    def prerequisites_callable(
        self, config: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        if not config:
            return False, "No configuration provided"

        try:
            nr_config = NewrelicConfig(**config)
            self.nr_account_id = nr_config.nr_account_id
            self.nr_api_key = nr_config.nr_api_key
            self.is_eu_datacenter = nr_config.is_eu_datacenter or False

            if not self.nr_account_id or not self.nr_api_key:
                return False, "New Relic account ID or API key is missing"

            return True, None
        except Exception as e:
            logging.exception("Failed to set up New Relic toolset")
            return False, str(e)

    def call_nerdql(self):
        pass

    def get_example_config(self) -> Dict[str, Any]:
        return {}
