import argparse
import json
import os
import random
import string
import threading
import time
import uuid

import requests

# -------- Env validation (exact style requested) --------
if not (
    (os.environ.get("NEW_RELIC_ACCOUNT_ID") or "")
    and (os.environ.get("NEW_RELIC_API_KEY") or "")
    and (os.environ.get("NEW_RELIC_LICENSE_KEY") or "")
):
    for v in ["NEW_RELIC_ACCOUNT_ID", "NEW_RELIC_API_KEY", "NEW_RELIC_LICENSE_KEY"]:
        if not os.environ.get(v):
            print(f"Missing env var: {v}")
    raise SystemExit(1)

ACCOUNT_ID = os.environ["NEW_RELIC_ACCOUNT_ID"]
ADMIN_API_KEY = os.environ["NEW_RELIC_API_KEY"]  # NerdGraph / Admin key (unused here)
INSERT_KEY = os.environ[
    "NEW_RELIC_LICENSE_KEY"
]  # Insert/License key for metrics/logs/traces/events

# Endpoints (override via env if needed)
METRIC_URL = os.environ.get(
    "NR_METRIC_URL", "https://metric-api.newrelic.com/metric/v1"
)
LOG_URL = os.environ.get("NR_LOG_URL", "https://log-api.newrelic.com/log/v1")
EVENT_URL = os.environ.get(
    "NR_EVENT_URL",
    f"https://insights-collector.newrelic.com/v1/accounts/{ACCOUNT_ID}/events",
)
TRACE_URL = os.environ.get("NR_TRACE_URL", "https://otlp.nr-data.net:4318/v1/traces")

# --- add near the top with your endpoints ---
OTLP_METRIC_URL = os.environ.get(
    "NR_OTLP_METRIC_URL", "https://otlp.nr-data.net:4318/v1/metrics"
)


def post_otlp_metrics(resource_metrics):
    headers = {"Content-Type": "application/json", "api-key": INSERT_KEY}
    try:
        r = requests.post(
            OTLP_METRIC_URL, headers=headers, json=resource_metrics, timeout=10
        )
        r.raise_for_status()
    except Exception as e:
        print("otlp metric post error:", e)


def emit_http_server_metric(
    service_name,
    run_env,
    route,
    method,
    status_code,
    duration_ms,
    resource_extra=None,
    span_attrs=None,
):
    """
    Emit a single OTel Histogram point for http.server.request.duration (seconds).
    This drives New Relic's apm.service.transaction.duration synthesis.
    """
    now_ns = int(time.time() * 1e9)
    dur_s = max(0.0, float(duration_ms) / 1000.0)

    # simple bucket scheme (seconds) to place our single sample
    bounds = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5]
    bucket_counts = [0] * (len(bounds) + 1)
    idx = 0
    while idx < len(bounds) and dur_s > bounds[idx]:
        idx += 1
    bucket_counts[idx] = 1

    # resource attributes (must match the service entity)
    res = {
        "service.name": service_name,
        "deployment.environment": run_env,
        "telemetry.sdk.name": "opentelemetry",
        "telemetry.sdk.language": "python",
        "service.instance.id": str(uuid.uuid4()),
    }
    if resource_extra:
        res.update(resource_extra)

    # point attributes (HTTP dims)
    attrs = {
        "http.method": method,
        "http.request.method": method,
        "http.route": route,
        "http.target": route,
        "http.response.status_code": int(status_code),
    }
    if span_attrs:
        attrs.update(span_attrs)

    payload = {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": k, "value": {"stringValue": str(v)}}
                        for k, v in res.items()
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {"name": "retail-sim", "version": "1.0.0"},
                        "metrics": [
                            {
                                "name": "http.server.request.duration",
                                "unit": "s",
                                "histogram": {
                                    "dataPoints": [
                                        {
                                            "startTimeUnixNano": now_ns,  # single sample window
                                            "timeUnixNano": now_ns,
                                            "count": "1",
                                            "sum": dur_s,
                                            "bucketCounts": [
                                                str(c) for c in bucket_counts
                                            ],
                                            "explicitBounds": bounds,
                                            "attributes": [
                                                {
                                                    "key": k,
                                                    "value": {"stringValue": str(v)},
                                                }
                                                for k, v in attrs.items()
                                            ],
                                        }
                                    ],
                                    "aggregationTemporality": "AGGREGATION_TEMPORALITY_DELTA",
                                },
                            }
                        ],
                    }
                ],
            }
        ]
    }
    post_otlp_metrics(payload)


def now_ms():
    return int(time.time() * 1000)


def random_choice_weighted(weight_map):
    items = list(weight_map.items())
    keys = [k for k, _ in items]
    weights = [w for _, w in items]
    return random.choices(keys, weights=weights, k=1)[0]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def p(prob):
    return random.random() < prob


def rand_sku():
    return "SKU-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def make_ids(seed_attrs=None):
    """
    Build a bundle of IDs we can inject into logs and spans.
    """
    bundle = {
        "userId": f"usr-{uuid.uuid4().hex[:8]}",
        "sessionId": f"sess-{uuid.uuid4().hex[:8]}",
        "orderId": f"ord-{random.randint(100000, 999999)}",
        "paymentId": f"pay-{uuid.uuid4().hex[:8]}",
        "txnId": f"txn-{uuid.uuid4().hex[:8]}",
        "productSku": rand_sku(),
    }
    if seed_attrs:
        bundle.update({k: v for k, v in seed_attrs.items() if k in bundle})
    return bundle


def expand_template(msg, ids_dict, attrs_dict):
    """
    Expand {userId}, {orderId}, etc. in a message safely.
    Unknown placeholders are left as-is.
    """

    class SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    try:
        return msg.format_map(SafeDict({**ids_dict, **attrs_dict}))
    except Exception:
        return msg


# ---------------------------------------------------------------------------
# New Relic POST helpers
# ---------------------------------------------------------------------------


def post_metrics(payload):
    headers = {"Content-Type": "application/json", "Api-Key": INSERT_KEY}
    try:
        r = requests.post(METRIC_URL, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print("metric post error:", e)


def post_logs(payload):
    # Accepts either the Telemetry SDK 'common/logs' shape or a plain list of log objects.
    # New Relic Log API accepts License or Api-Key headers. We use License for clarity.  # docs: https://docs.newrelic.com/docs/logs/log-api/introduction-log-api/
    headers = {"Content-Type": "application/json", "X-License-Key": INSERT_KEY}
    try:
        r = requests.post(LOG_URL, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print("log post error:", e)


def post_events(payload):
    headers = {"Content-Type": "application/json", "X-Insert-Key": INSERT_KEY}
    try:
        body = payload if isinstance(payload, list) else [payload]
        r = requests.post(EVENT_URL, headers=headers, json=body, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print("event post error:", e)


def post_traces(otlp_resource_spans):
    """
    Send OTLP/HTTP trace payload to New Relic.
    """
    headers = {"Content-Type": "application/json", "api-key": INSERT_KEY}
    try:
        r = requests.post(
            TRACE_URL, headers=headers, json=otlp_resource_spans, timeout=10
        )
        r.raise_for_status()
    except Exception as e:
        print("trace post error:", e)


# ---------------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------------


def emit_metric_point(run_env, metric, common_attrs):
    """
    Emits one metric data point. Count/summary include interval.ms=1000 since we emit each second.
    """
    ts = now_ms()
    name = metric["name"]
    mtype = metric.get("type", "gauge")
    lo, hi = metric.get("min", 0), metric.get("max", 1)
    value = random.uniform(lo, hi)

    if name.endswith(".ratio"):
        value = clamp(random.uniform(lo, hi), 0, 1)
    if name.endswith(".count"):
        value = int(random.uniform(lo, hi))

    point = {
        "name": name,
        "type": mtype,
        "value": value,
        "timestamp": ts,
        "attributes": {**common_attrs, "env": run_env},
    }
    if mtype in ("count", "summary"):
        point["interval.ms"] = 1000  # 1s
    post_metrics([{"metrics": [point]}])


def emit_transaction_event(run_env, txn_spec, common_attrs):
    event = {
        "eventType": "RetailTransaction",
        "timestamp": now_ms(),
        **common_attrs,
        "env": run_env,
    }
    kpis = txn_spec.get("kpi", {})
    for k, rng in kpis.items():
        lo, hi = rng.get("min", 0), rng.get("max", 1)
        event[k] = (
            int(random.uniform(lo, hi))
            if k.endswith(".count")
            else random.uniform(lo, hi)
        )
    for k, v in txn_spec.get("attrs", {}).items():
        event[k] = v
    post_events(event)


def otlp_attr(key, value, vtype=None):
    if vtype is None:
        if isinstance(value, bool):
            vtype = "bool"
        elif isinstance(value, int):
            vtype = "int"
        elif isinstance(value, float):
            vtype = "double"
        else:
            vtype = "string"
    return {"key": key, "value": {f"{vtype}Value": value}}


def emit_trace_with_spans(run_env, trace_spec, common_attrs):
    """
    Emits OTLP/HTTP traces that New Relic synthesizes into APM Web transactions.

    Non-negotiables for APM synthesis:
      • Root span MUST be SPAN_KIND_SERVER.
      • Root span MUST look like an HTTP server span: include http.method/route + a status code.
      • Resource MUST include service.name (stable APM entity name).
      • Use deployment.environment=<run_env> to scope dashboards/queries.

    Result:
      • APM entity per service.name (frontend, payments, etc.)
      • Metric: apm.service.transaction.duration (queryable from Metric)
      • UI: Transactions list + Distributed tracing
    """
    trace_id = uuid.uuid4().hex
    ids_bundle = make_ids()

    # Group spans by service so each service gets its own resourceSpans block
    spans_by_service = {}
    parent_id = None

    for idx, s in enumerate(trace_spec.get("spans", [])):
        # pacing between spans
        dlo, dhi = s.get("delay_ms", [0, 0])
        if dlo or dhi:
            time.sleep(random.uniform(dlo, dhi) / 1000.0)

        service = s.get("service", s.get("name", "service"))
        span_id = uuid.uuid4().hex[:16]
        dur_ms = random.uniform(s.get("min_ms", 30), s.get("max_ms", 180))
        start_ns = int(time.time() * 1e9)
        end_ns = start_ns + int(dur_ms * 1e6)

        is_root = idx == 0
        span_kind = "SPAN_KIND_SERVER" if is_root else "SPAN_KIND_INTERNAL"

        op_base = s.get("name", "op")

        # NEW: allow JSON to set explicit HTTP method/route (defaults keep old behavior)
        method = (s.get("method") or "GET").upper()
        route = s.get("route") or ("/" + op_base if is_root else op_base)

        # Name the ROOT span like "GET /pay" so Transactions list shows the desired name
        span_name = f"{method} {route}" if is_root else op_base

        # Error behavior unchanged...
        errored = p(s.get("error_prob", 0.0))
        status_code = 2 if errored else 1
        http_status = 500 if errored else 200

        span_attrs = {
            **s.get("attributes", {}),
            **common_attrs,
            "env": run_env,
            "otel.span.service": service,
        }

        if is_root:
            # Drive APM via OTel HTTP server metric with SAME method/route
            emit_http_server_metric(
                service_name=service,
                run_env=run_env,
                route=route,
                method=method,  # <— was hardcoded "GET"
                status_code=http_status,
                duration_ms=dur_ms,
                resource_extra=common_attrs,
                span_attrs=None,
            )

            # CRITICAL: put HTTP server attrs on the ROOT span too
            span_attrs.update(
                {
                    "http.method": method,
                    "http.route": route,  # normalized route (e.g., /pay)
                    "http.target": route,  # backward-compatible path
                    "url.path": route,  # classic alias
                    "http.response.status_code": http_status,
                    "http.status_code": http_status,  # classic alias
                }
            )

        span = {
            "traceId": trace_id,
            "spanId": span_id,
            "name": span_name,
            "kind": span_kind,
            "startTimeUnixNano": start_ns,
            "endTimeUnixNano": end_ns,
            "attributes": [otlp_attr(k, v) for k, v in span_attrs.items()],
            "status": {"code": status_code},
        }
        if parent_id and not is_root:
            span["parentSpanId"] = parent_id

        spans_by_service.setdefault(service, []).append(span)
        parent_id = span_id

        # Optional correlated logs (INFO/WARN) tied to this span
        for level_key, msgs in (
            ("info_logs", s.get("info_logs", [])),
            ("warn_logs", s.get("warn_logs", [])),
        ):
            if not msgs:
                continue
            lvl = "INFO" if level_key == "info_logs" else "WARN"
            post_logs(
                [
                    {
                        "common": {
                            "attributes": {
                                "service.name": service,
                                "env": run_env,
                                **common_attrs,
                                "trace.id": trace_id,
                                "span.id": span_id,
                                "user.id": ids_bundle["userId"],
                                "ecommerce.order.id": ids_bundle["orderId"],
                                "ecommerce.payment.id": ids_bundle["paymentId"],
                                "ecommerce.txn.id": ids_bundle["txnId"],
                            }
                        },
                        "logs": [
                            {
                                "timestamp": now_ms(),
                                "message": expand_template(
                                    random.choice(msgs), ids_bundle, common_attrs
                                ),
                                "level": lvl,
                            }
                        ],
                    }
                ]
            )

    # One resource block per service (stable entity per service.name)
    resource_spans = []
    for service, spans in spans_by_service.items():
        resource_attrs = {
            "service.name": service,  # APM/OTel entity name
            "service.namespace": run_env,  # <-- add: used for APM-style scoping
            "deployment.environment": run_env,
            "service.instance.id": str(uuid.uuid4()),
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",  # <-- add: makes entity classification explicit
            **common_attrs,
            "env": run_env,
        }

        resource_spans.append(
            {
                "resource": {
                    "attributes": [otlp_attr(k, v) for k, v in resource_attrs.items()]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "retail-sim", "version": "1.0.0"},
                        "spans": spans,
                    }
                ],
            }
        )

    post_traces({"resourceSpans": resource_spans})


def maybe_emit_background_logs(run_env, scenario, base_attrs):
    cfg = scenario.get("logs")
    if not cfg:
        return
    svc = cfg.get("service_name", base_attrs.get("service", "frontend"))
    info_rpm = max(0, int(cfg.get("info_rate_per_min", 0)))
    warn_rpm = max(0, int(cfg.get("warn_rate_per_min", 0)))
    info_msgs = cfg.get("info_messages", [])
    warn_msgs = cfg.get("warn_messages", [])

    # probabilistic per-second emission based on rpm
    def should(rate_per_min):
        if rate_per_min <= 0:
            return False
        return random.random() < (rate_per_min / 60.0)

    ids_bundle = make_ids()
    logs = []
    if should(info_rpm) and info_msgs:
        logs.append(
            {
                "timestamp": now_ms(),
                "message": expand_template(
                    random.choice(info_msgs), ids_bundle, base_attrs
                ),
                "level": "INFO",
            }
        )
    if should(warn_rpm) and warn_msgs:
        logs.append(
            {
                "timestamp": now_ms(),
                "message": expand_template(
                    random.choice(warn_msgs), ids_bundle, base_attrs
                ),
                "level": "WARN",
            }
        )
    if logs:
        post_logs(
            [
                {
                    "common": {
                        "attributes": {
                            "service.name": svc,
                            "env": run_env,
                            **base_attrs,
                        }
                    },
                    "logs": logs,
                }
            ]
        )


# ---------------------------------------------------------------------------
# Scenario thread
# ---------------------------------------------------------------------------


def scenario_thread(run_env, scenario, stop_after_s=None):
    thread_name = scenario.get("name", "scenario")
    random.seed(scenario.get("seed", 42))
    print(f"[{thread_name}] start env={run_env}")

    trace_rate = scenario.get("trace_rate_per_min", 120)

    next_trace_ts = time.time()

    t0 = time.time()
    while True:
        if stop_after_s and (time.time() - t0) > stop_after_s:
            print(f"[{thread_name}] stopping after {stop_after_s}s")
            break

        base_attrs = dict(scenario.get("common", {}))
        dists = scenario.get("distributions", {})
        if "country" in dists:
            base_attrs["country"] = random_choice_weighted(dists["country"])
        if "device" in dists:
            base_attrs["device"] = random_choice_weighted(dists["device"])
        if "paymentMethod" in dists:
            base_attrs["paymentMethod"] = random_choice_weighted(dists["paymentMethod"])
        if "category" in dists:
            base_attrs["category"] = random_choice_weighted(dists["category"])
        # high-cardinality occasionally
        if p(scenario.get("session_cardinality_rate", 0.3)):
            base_attrs["sessionId"] = f"sess-{uuid.uuid4().hex[:8]}"
        if p(scenario.get("sku_cardinality_rate", 0.2)):
            base_attrs["productSku"] = rand_sku()

        # (1) Metrics each second
        for m in scenario.get("metrics", []):
            emit_metric_point(run_env, m, base_attrs)

        # (2) Traces at configured rate → APM Transactions
        now = time.time()
        if now >= next_trace_ts and scenario.get("traces"):
            next_trace_ts = now + 60.0 / max(1, trace_rate)
            trace_spec = random.choice(scenario["traces"])
            emit_trace_with_spans(run_env, trace_spec, base_attrs)

        # (3) Background logs (optional per-scenario config)
        maybe_emit_background_logs(run_env, scenario, base_attrs)

        time.sleep(1.0)


# ---------------------------------------------------------------------------
# Dashboards (NerdGraph) — dynamic from the JSON spec (fixed schema)
# ---------------------------------------------------------------------------
# ---------- NerdGraph helpers ----------
def _nrgraphql(query: str, variables: dict):
    url = "https://api.newrelic.com/graphql"
    headers = {"Content-Type": "application/json", "API-Key": ADMIN_API_KEY}
    r = requests.post(
        url, headers=headers, json={"query": query, "variables": variables}, timeout=30
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data and data["errors"]:
        raise RuntimeError("NerdGraph errors: " + json.dumps(data["errors"])[:600])
    return data


def _find_dashboards_by_name(name: str):
    q = """
      query ($query: String!) {
        actor {
          entitySearch(query: $query) {
            results { entities { guid name accountId type } }
          }
        }
      }
    """
    query_str = f"name = '{name}' AND type = 'DASHBOARD'"
    data = _nrgraphql(q, {"query": query_str})
    ents = (
        data.get("data", {})
        .get("actor", {})
        .get("entitySearch", {})
        .get("results", {})
        .get("entities", [])
    )
    return [e for e in ents if e.get("name") == name]


def _delete_dashboard(account_id: int, guid: str):
    m = """
      mutation DeleteDashboard($guid: EntityGuid!) {
        dashboardDelete(guid: $guid) { status }
      }
    """
    _nrgraphql(m, {"accountId": int(account_id), "guid": guid})


def _find_apm_entities_for_env(run_env: str, candidate_services: list):
    """
    Return list of {guid, name} for APM/OTel services that have deployment.environment=run_env
    and (optionally) whose names appear in candidate_services (if provided).
    We search both SERVICE and APPLICATION types across APM/OTel domains.
    """
    names_filter = ""
    if candidate_services:
        # narrow by names we actually emit in traces
        quoted = " OR ".join([f"name = '{n}'" for n in set(candidate_services)])
        names_filter = f" AND ({quoted})"

    q = """
      query($query: String!) {
        actor {
          entitySearch(query: $query) {
            results {
              entities { guid name type domain reporting }
            }
          }
        }
      }
    """
    query_str = (
        "type IN ('SERVICE','APPLICATION') "
        "AND (domain IN ('APM','EXT','EBPF')) "
        f"AND tags.deployment.environment = '{run_env}'"
        f"{names_filter}"
    )
    data = _nrgraphql(q, {"query": query_str})
    ents = (
        data.get("data", {})
        .get("actor", {})
        .get("entitySearch", {})
        .get("results", {})
        .get("entities", [])
    )
    # keep only reporting entities (actively sending)
    return [{"guid": e["guid"], "name": e["name"]} for e in ents if e.get("reporting")]


# ---------------------------------------------------------------------------
# Dashboards (delete+recreate) — ONLY APM Transactions + metrics/traces/logs
# ---------------------------------------------------------------------------
def create_or_update_dashboards(run_env, scenarios, title_prefix="Retail AIOps Demo"):
    acct = int(ACCOUNT_ID)
    ENV = run_env
    final_name = f"{title_prefix} • {ENV}"

    # 1) delete any existing with same name
    try:
        existing = _find_dashboards_by_name(final_name)
        for ent in existing:
            try:
                _delete_dashboard(ent["accountId"], ent["guid"])
                print(f"[dashboard] Deleted existing: {ent['name']} ({ent['guid']})")
            except Exception as de:
                print(f"[dashboard] Delete failed for {ent.get('guid')}: {de}")
    except Exception as se:
        print(f"[dashboard] Search/delete preflight failed: {se}")

    # 2) derive dynamic bits from spec
    metric_names, services = set(), set()
    has_traces, has_logs = False, False
    for sc in scenarios:
        for m in sc.get("metrics", []):
            if "name" in m:
                metric_names.add(m["name"])
        for tr in sc.get("traces", []):
            has_traces = True
            for sp in tr.get("spans", []):
                svc = sp.get("service") or sp.get("name")
                if svc:
                    services.add(svc)
        if sc.get("logs"):
            has_logs = True

    metric_names = sorted(metric_names)
    services = sorted(services)

    # 3) discover entity GUIDs for this env + services
    apm_entities = _find_apm_entities_for_env(ENV, services)
    entity_guids = [e["guid"] for e in apm_entities]
    # build an IN (...) filter; if none found yet, use an impossible guid to keep panel valid
    guid_list = "', '".join(entity_guids) if entity_guids else "0000000000000000"
    guid_filter = (
        f"entity.guid IN ('{guid_list}')"
        if entity_guids
        else "entity.guid = '0000000000000000'"
    )

    # 4) widget helpers
    VIZ = {
        "LINE_CHART": "viz.line",
        "BAR_CHART": "viz.bar",
        "TABLE": "viz.table",
        "BILLBOARD": "viz.billboard",
    }

    def w(title, viz_key, col, row, width, height, *queries):
        return {
            "title": title,
            "layout": {"column": col, "row": row, "width": width, "height": height},
            "visualization": {"id": VIZ[viz_key]},
            "rawConfiguration": {
                "nrqlQueries": [{"accountId": acct, "query": q} for q in queries]
            },
        }

    def agg_for_metric(name, mtype="gauge"):
        n = name.lower()
        if mtype == "count" or n.endswith(".count"):
            return (
                lambda metric: f"FROM Metric SELECT rate(sum(`{metric}`), 1 minute) WHERE env = '{ENV}' SINCE 30 minutes ago TIMESERIES"
            )
        if n.endswith(".ratio") or n.endswith(".duration.ms"):
            return (
                lambda metric: f"FROM Metric SELECT average(`{metric}`) WHERE env = '{ENV}' SINCE 30 minutes ago TIMESERIES"
            )
        return (
            lambda metric: f"FROM Metric SELECT average(`{metric}`) WHERE env = '{ENV}' SINCE 30 minutes ago TIMESERIES"
        )

    col, row = 1, 1

    def place(next_width=4, next_height=3):
        nonlocal col, row
        c, r = col, row
        col += next_width
        if col > 12:
            col = 1
            row += next_height
            c, r = 1, row
        return c, r

    widgets = []

    # Metrics (from your spec)
    for m in metric_names:
        mtype = "count" if m.endswith(".count") else "gauge"
        q = agg_for_metric(m, mtype)(m)
        c, r = place()
        widgets.append(w(m, "LINE_CHART", c, r, 4, 3, q))

    # Traces/Services (Span data)
    if has_traces:
        q_traces_by_svc = f"FROM Span SELECT uniqueCount(traceId) WHERE env = '{ENV}' SINCE 30 minutes ago FACET `service.name` LIMIT 10"
        c, r = place()
        widgets.append(w("Traces by service", "BAR_CHART", c, r, 4, 3, q_traces_by_svc))

        q_p95_all = f"FROM Span SELECT percentile(duration, 95) WHERE env = '{ENV}' SINCE 30 minutes ago FACET `service.name` LIMIT 10 TIMESERIES"
        c, r = place()
        widgets.append(w("p95 by service", "LINE_CHART", c, r, 8, 3, q_p95_all))

        q_trace_groups = f"FROM Span SELECT uniqueCount(traceId) WHERE env = '{ENV}' SINCE 30 minutes ago FACET name LIMIT 15"
        c, r = place()
        widgets.append(w("Trace groups", "BAR_CHART", c, r, 4, 3, q_trace_groups))

        q_services_tbl = f"FROM Span SELECT uniqueCount(traceId) AS 'Traces' WHERE env = '{ENV}' SINCE 30 minutes ago FACET `service.name` LIMIT 20"
        c, r = place(12, 4)
        widgets.append(w("Services (last 30m)", "TABLE", c, r, 12, 4, q_services_tbl))

    # *** APM Transactions (entity-linked via entity.guid) ***
    q_txn_rate = (
        "FROM Metric "
        "SELECT rate(count(apm.service.transaction.duration), 1 minute) "
        f"WHERE metricName = 'apm.service.transaction.duration' AND {guid_filter} "
        "SINCE 30 minutes ago TIMESERIES FACET entity.name LIMIT 12"
    )
    c, r = place(12, 3)
    widgets.append(
        w("APM Transactions/min (by entity)", "LINE_CHART", c, r, 12, 3, q_txn_rate)
    )

    # Logs (if present)
    if has_logs:
        q_logs_rate = f"FROM Log SELECT rate(count(*), 1 minute) WHERE env = '{ENV}' SINCE 30 minutes ago TIMESERIES"
        q_logs_level = f"FROM Log SELECT count(*) WHERE env = '{ENV}' SINCE 30 minutes ago FACET level LIMIT 6"
        c, r = place()
        widgets.append(w("Logs/min", "LINE_CHART", c, r, 6, 3, q_logs_rate))
        c, r = place()
        widgets.append(w("Logs by level", "BAR_CHART", c, r, 6, 3, q_logs_level))
        q_logs_svc = f"FROM Log SELECT count(*) WHERE env = '{ENV}' SINCE 30 minutes ago FACET `service.name` LIMIT 10"
        c, r = place(12, 3)
        widgets.append(w("Logs by service", "BAR_CHART", c, r, 12, 3, q_logs_svc))

    dashboard = {
        "name": final_name,
        "description": "Auto-generated from Retail AIOps JSON spec",
        "permissions": "PUBLIC_READ_WRITE",
        "pages": [
            {
                "name": "Overview",
                "description": f"Scoped to env = {ENV}",
                "widgets": widgets,
            }
        ],
    }

    mutation = """
      mutation($accountId: Int!, $dashboard: DashboardInput!) {
        dashboardCreate(accountId: $accountId, dashboard: $dashboard) {
          entityResult { guid name }
          errors { description type }
        }
      }
    """

    data = _nrgraphql(mutation, {"accountId": acct, "dashboard": dashboard})
    result = data.get("data", {}).get("dashboardCreate", {})
    if result.get("errors"):
        raise RuntimeError(
            "Dashboard mutation errors: " + json.dumps(result["errors"])[:600]
        )

    ent = result.get("entityResult") or {}
    guid = ent.get("guid")
    name = ent.get("name")
    if not guid:
        raise RuntimeError("No dashboard GUID returned: " + json.dumps(data)[:600])

    url = f"https://one.newrelic.com/dashboards/{guid}?account={acct}"
    print(f"[dashboard] Created: {name}\n[dashboard] URL: {url}")
    return url


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec", default="specs.json", help="Path to scenarios JSON (list)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Max seconds to run each scenario thread (safety cap)",
    )
    parser.add_argument(
        "--create-dashboards",
        action="store_true",
        help="Create/Update dashboards for this run scope (stub)",
    )
    args = parser.parse_args()

    run_env = os.environ.get("DEMO_ENV", "app-124")
    print(f"[run] env={run_env}")

    random.seed(run_env)

    with open(args.spec, "r") as f:
        scenarios = json.load(f)

    try:
        if args.create_dashboards:
            create_or_update_dashboards(run_env, scenarios)
    except Exception as e:
        print(f"Error making dashboards {e}")

    threads = []
    for sc in scenarios:
        t = threading.Thread(
            target=scenario_thread, args=(run_env, sc, args.duration), daemon=True
        )
        t.start()
        threads.append(t)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("Interrupted, exiting.")


if __name__ == "__main__":
    main()
