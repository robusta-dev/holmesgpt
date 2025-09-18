from typing import Any, Dict, List, Optional, Tuple, Union, Literal
from datetime import datetime, timezone
from collections import defaultdict
from pydantic import BaseModel, Field
import uuid
import math


class PromSeries(BaseModel):
    metric: Dict[str, Any]
    values: List[List[Union[int, str]]]


class PromData(BaseModel):
    resultType: Literal["matrix"] = "matrix"
    result: List[PromSeries] = Field(default_factory=list)


class PromResponse(BaseModel):
    status: Literal["success", "error"] = "success"
    error_message: Optional[str] = None
    random_key: str = Field(default_factory=lambda: uuid.uuid4().hex)
    tool_name: str
    description: str = ""
    query: str = ""
    start: str = ""
    end: str = ""
    step: int = 60
    output_type: str = "Plain"
    data: PromData = Field(default_factory=PromData)
    # Include raw payload on error (or when desired)
    raw: Optional[Any] = None

    # ---- helpers ----
    @staticmethod
    def _rfc3339(ts: Optional[int]) -> str:
        if ts is None:
            return ""
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    @staticmethod
    def _to_prom_value(v: Any) -> str:
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

    @classmethod
    def empty_success(
        cls,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> "PromResponse":
        params = params or {}
        return cls(
            status="success",
            error_message=None,
            tool_name=tool_name,
            description=params.get("description", ""),
            query=params.get("query", ""),
            start="",
            end="",
            step=60,
            output_type=params.get("output_type", "Plain"),
            data=PromData(resultType="matrix", result=[]),
        )

    @classmethod
    def error(
        cls,
        tool_name: str,
        params: Optional[Dict[str, Any]],
        message: str,
        raw: Any = None,
    ) -> "PromResponse":
        params = params or {}
        return cls(
            status="error",
            error_message=message,
            tool_name=tool_name,
            description=params.get("description", ""),
            query=params.get("query", ""),
            start="",
            end="",
            step=60,
            output_type=params.get("output_type", "Plain"),
            data=PromData(resultType="matrix", result=[]),
            raw=raw,  # <-- include the raw payload on error
        )

    def to_json(self) -> Dict[str, Any]:
        """
        Return a plain JSON-serializable dict (works on Pydantic v1/v2).
        """
        dump = getattr(self, "model_dump", None)
        return dump() if dump else self.dict()

    @classmethod
    def from_newrelic_records(
        cls,
        *,
        records: List[Dict[str, Any]],
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        begin_key: str = "beginTimeSeconds",
        end_key: str = "endTimeSeconds",
        facet_key: str = "facet",
    ) -> "PromResponse":
        """
        Safe builder with try/except that transforms New Relic NerdGraph results
        into a Prometheus-like response wrapped in Pydantic models.
        On error: returns an error response WITH the raw data at `raw`.
        """
        params = params or {}

        try:
            if not records:
                return cls.empty_success(tool_name=tool_name, params=params)

            # All keys across records
            all_keys = set().union(*(r.keys() for r in records))

            # Reserved/time-ish keys
            reserved = {begin_key, end_key, facet_key, "timestamp"}

            # Find metric keys (prefer aggregated names like "average.duration")
            known_metric_singletons = {"count", "rate", "apdex"}
            metric_keys: set = set()
            for k in all_keys - reserved:
                if "." in k or k in known_metric_singletons:
                    metric_keys.add(k)

            # Fallback: any key that has numeric/None values in at least one record
            if not metric_keys:
                for k in all_keys - reserved:
                    if any(
                        isinstance(r.get(k), (int, float)) or r.get(k) is None
                        for r in records
                    ):
                        metric_keys.add(k)

            # Label keys are the rest (we'll filter reserved when grouping)
            label_keys = sorted(all_keys - metric_keys)

            # Determine global start/end
            begins = [
                r.get(begin_key)
                for r in records
                if isinstance(r.get(begin_key), (int, float))
            ]
            ends = [
                r.get(end_key)
                for r in records
                if isinstance(r.get(end_key), (int, float))
            ]
            start_ts = min(begins) if begins else (min(ends) if ends else None)  # type: ignore[type-var]
            end_ts = max(ends) if ends else (max(begins) if begins else None)  # type: ignore[type-var]

            # Step: prefer most common (end - begin) delta; else infer from end timestamps; else 60
            deltas = [
                int(r[end_key] - r[begin_key])
                for r in records
                if isinstance(r.get(end_key), (int, float))
                and isinstance(r.get(begin_key), (int, float))
            ]
            if deltas:
                step = max(set(deltas), key=deltas.count)
            else:
                sorted_ends = sorted([int(e) for e in ends]) if ends else []  # type: ignore[arg-type]
                consec = [b - a for a, b in zip(sorted_ends, sorted_ends[1:])]
                step = max(set(consec), key=consec.count) if consec else 60

            # Group by labels (excluding metric keys and reserved at group time)
            def label_tuple(rec: Dict[str, Any]) -> Tuple[Tuple[str, Any], ...]:
                items = []
                for k in label_keys:
                    if k in reserved:
                        continue
                    if k in rec:
                        items.append((k, rec.get(k)))
                return tuple(sorted(items))

            groups: Dict[Tuple[Tuple[str, Any], ...], List[Dict[str, Any]]] = (
                defaultdict(list)
            )
            for rec in records:
                groups[label_tuple(rec)].append(rec)

            prom_series: List[PromSeries] = []

            for lt, recs in groups.items():
                labels = {k: v for (k, v) in lt}

                # Sort buckets by end time then begin time (kept from original logic)
                recs_sorted = sorted(
                    recs,
                    key=lambda r: (
                        r.get(end_key) is None,
                        r.get(end_key),
                        r.get(begin_key),
                    ),
                )

                for mkey in sorted(metric_keys):
                    metric = {"__name__": mkey}
                    metric.update(labels)

                    values: List[List[Union[int, str]]] = []
                    for r in recs_sorted:
                        ts = r.get(end_key) or r.get(begin_key)
                        if not isinstance(ts, (int, float)):
                            continue
                        v = cls._to_prom_value(r.get(mkey))
                        values.append([int(ts), v])

                    if values:
                        prom_series.append(PromSeries(metric=metric, values=values))

            data = PromData(resultType="matrix", result=prom_series)

            return cls(
                status="success",
                error_message=None,
                tool_name=tool_name,
                description=params.get("description", ""),
                query=params.get("query", ""),
                start=cls._rfc3339(int(start_ts)) if start_ts is not None else "",
                end=cls._rfc3339(int(end_ts)) if end_ts is not None else "",
                step=int(step),
                output_type=params.get("output_type", "Plain"),
                data=data,
            )

        except Exception as e:
            # On error: return the raw data JSON in the response
            return cls.error(
                tool_name=tool_name,
                params=params,
                message=str(e),
                raw={"records": records, "params": params},
            )
