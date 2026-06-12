"""resource-flow anomaly detection primitive — LangServer.

Task types:
  resource-flow.detect.anomaly
  resource-flow.project.flow
  resource-flow.review.anomaly
BPMN:      00-contracts/bpmn/com/etzhayyim/resource-flow/detectAnomaly.bpmn (R/PT24H)

Ported from 60-apps/etzhayyim-project-resource-flow/worker/src/app.ts detectAnomaly().
Covers all 3 flow classes: currency, service, personnel.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import decimal as _decimal
import json
import logging
import time
import uuid
from typing import Any
from urllib.parse import quote


LOG = logging.getLogger("resource_flow.detect")

_PRIMARY_DID = "did:web:resource-flow.etzhayyim.com"
_BPMN_REPO   = "did:web:bpmn.etzhayyim.com"

_FLOW_CLASSES = ("currency", "service", "personnel")

_SANKEY_TABLES: dict[str, str] = {
    "currency":  "mv_resource_flow_sankey_currency",
    "service":   "mv_resource_flow_sankey_service",
    "personnel": "mv_resource_flow_sankey_personnel",
}

_FLOW_TABLES: dict[str, str] = {
    "currency": "vertex_resource_flow_currency",
    "service": "vertex_resource_flow_service",
    "personnel": "vertex_resource_flow_personnel",
}

_DOMAIN_INDUSTRY: dict[str, tuple[str, ...]] = {
    "hospitality": ("I5510", "I5520", "N7911"),
    "transport": ("H4911", "H5110", "H5210"),
    "manufacturing": ("C2410", "C2620", "C2910"),
}

_LEGAL_ENTITY_PREFIXES = (
    "did:web:legal-entity.etzhayyim.com:lei:",
    "did:web:hospitality.etzhayyim.com:actor:",
    "did:web:transport.etzhayyim.com:actor:",
    "did:web:manufacturing.etzhayyim.com:actor:",
    "did:web:gov-",
    "did:web:resource-flow.etzhayyim.com",
    "did:web:yadoya.etzhayyim.com",
    "did:web:minpaku.etzhayyim.com",
)

_ANOMALY_REVIEW_TABLE = "vertex_resource_flow_anomaly_review"
_ANOMALY_TABLE = "vertex_resource_flow_anomaly"
_ANOMALY_ACTIONS = {"acknowledge", "dismiss", "escalate"}


def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _run_id() -> str:
    return f"r{uuid.uuid4().hex[:14]}"


def _str(v: Any) -> str:
    return "" if v is None else str(v)


def _num(v: Any, default: float | None = 0) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int_or_none(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _is_legal_entity(did: str) -> bool:
    return not did or any(did.startswith(p) for p in _LEGAL_ENTITY_PREFIXES)


def _reject_individual(record: dict[str, Any]) -> str | None:
    cp = _str(record.get("counterpartyDid"))
    if cp and not _is_legal_entity(cp):
        return "counterpartyDid is not a recognized legal-entity DID"
    if record.get("cohortId"):
        size = _int_or_none(record.get("cohortSize")) or 0
        if size < 5:
            return "cohort_size must be >= 5 (ADR-0018)"
    return None


def _flow_vid(flow_class: str, record_uri: str) -> str:
    return (
        f"at://{_PRIMARY_DID}/com.etzhayyim.apps.resourceFlow."
        f"{flow_class}Projected/{quote(record_uri, safe='')}"
    )


def _review_id() -> str:
    return f"rv{uuid.uuid4().hex[:14]}"


def _review_vid(review_id: str) -> str:
    return f"at://{_PRIMARY_DID}/com.etzhayyim.apps.resourceFlow.anomalyReview/{review_id}"


def _facade_hash(did: str) -> str:
    return f"facade:{did}" if did else ""


def _identity_method(did: str) -> str:
    parts = did.split(":")
    return parts[1] if len(parts) > 2 and parts[0] == "did" else "web"


def _jsonable(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        return float(v)
    return v


def _rows_as_dicts(cur: Any, rows: list[Any]) -> list[dict[str, Any]]:
    cols = [d[0] for d in ([] or [])]
    return [{cols[i]: _jsonable(row[i]) for i in range(len(cols))} for row in rows]


def _bounded_int(v: Any, default: int, min_v: int, max_v: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    return max(min_v, min(max_v, n))


def _severity_for(ratio: float) -> str:
    if ratio >= 10:
        return "critical"
    if ratio >= 5:
        return "high"
    if ratio >= 3:
        return "medium"
    return "low"


def _anomaly_vid(run_id: str, flow_class: str, src: str, cp: str, period: str) -> str:
    slug = f"{run_id}:{flow_class}:{src}:{cp}:{period}"
    return f"at://{_PRIMARY_DID}/com.etzhayyim.apps.resourceFlow.anomaly/{quote(slug, safe='')}"


def _emit_anomaly_post(
    fc: str, src: str, cp: str, period: str,
    obs_val: float, baseline_avg: float, ratio: float,
    severity: str, window_days: int, baseline_n: int,
) -> None:
    from kotodama.primitives.yoro_social import insert_social_post_record  # noqa: PLC0415

    text = (
        f"⚠️ resource-flow anomaly ({severity})\n"
        f"{fc} {src} → {cp}\n"
        f"period={period} observed={obs_val:.0f} "
        f"baseline={baseline_avg:.2f} ratio={ratio:.2f}× "
        f"({window_days}d, n={baseline_n})"
    )
    rkey = f"rf-anomaly-{int(time.time() * 1000):x}"
    row = {
        "uri":          f"at://{_BPMN_REPO}/app.bsky.feed.post/{rkey}",
        "cid":          rkey,
        "collection":   "app.bsky.feed.post",
        "rkey":         rkey,
        "repo":         _BPMN_REPO,
        "repo_rev":     rkey,
        "value_json":   json.dumps(
            {"$type": "app.bsky.feed.post", "text": text[:300], "createdAt": _now_iso()},
            ensure_ascii=False,
        ),
        "indexed_at":   _now_iso(),
        "takedown_ref": None,
        "ts_ms":        int(time.time() * 1000),
        "created_at":   _now_iso(),
        "text":         text[:300],
    }
    try:
        insert_social_post_record(row, flush=False)
    except Exception as e:  # noqa: BLE001
        LOG.warning("anomaly post failed: %s", e)


def task_resource_flow_detect_anomaly(
    flowClass: str = "all",
    windowDays: int = 30,
    thresholdFactor: float = 3.0,
    minBaselineSamples: int = 3,
    post: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """Daily scan of mv_resource_flow_sankey_* for anomalous (source × counterparty) tuples.

    Uses a SQL CTE to compare the latest fiscal_period's event_count against the
    rolling N-period baseline. Tuples exceeding baseline_avg × thresholdFactor with
    at least minBaselineSamples baseline points are written to vertex_resource_flow_anomaly.
    High/critical anomalies emit a social AT post (C-path insert) when post=True.

    BPMN: resource_flow_detect_anomaly (R/PT24H timer-start).
    Task type: resource-flow.detect.anomaly
    """
    window_days  = max(1, min(365, int(windowDays)))
    threshold    = max(1.0, float(thresholdFactor))
    min_baseline = max(1, int(minBaselineSamples))

    classes = (
        _FLOW_CLASSES if str(flowClass).strip().lower() == "all"
        else (str(flowClass),)
    )

    run_id        = _run_id()
    observed_at   = _now_iso()
    total_scanned = 0
    total_flagged = 0

    for fc in classes:
        mv = _SANKEY_TABLES.get(fc)
        if not mv:
            LOG.warning("unknown flowClass=%s, skipping", fc)
            continue

        detection_sql = f"""
            WITH current_data AS (
                SELECT source_did, counterparty_did, fiscal_period,
                       industry_code, currency, service_class,
                       SUM(event_count) AS current_count
                FROM {mv}
                WHERE fiscal_period = (SELECT MAX(fiscal_period) FROM {mv})
                GROUP BY source_did, counterparty_did, fiscal_period,
                         industry_code, currency, service_class
            ),
            baseline_data AS (
                SELECT source_did, counterparty_did,
                       AVG(event_count) AS baseline_avg,
                       COUNT(*)         AS baseline_samples
                FROM {mv}
                WHERE fiscal_period < (SELECT MAX(fiscal_period) FROM {mv})
                GROUP BY source_did, counterparty_did
            )
            SELECT
                c.source_did, c.counterparty_did, c.fiscal_period,
                c.industry_code, c.currency, c.service_class,
                c.current_count AS observed_value,
                b.baseline_avg,
                b.baseline_samples AS baseline_sample_count,
                c.current_count / NULLIF(b.baseline_avg, 0) AS ratio
            FROM current_data c
            JOIN baseline_data b
              ON c.source_did       = b.source_did
             AND c.counterparty_did = b.counterparty_did
            WHERE b.baseline_samples >= {int(min_baseline)}
              AND b.baseline_avg > 0
              AND c.current_count > b.baseline_avg * {float(threshold)}
            LIMIT 500
        """

        count_sql = (
            f"SELECT COUNT(DISTINCT (source_did, counterparty_did)) "
            f"FROM {mv} "
            f"WHERE fiscal_period = (SELECT MAX(fiscal_period) FROM {mv})"
        )

        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(count_sql)
                count_row = (_res[0] if _res else None)
                total_scanned += int((count_row or [0])[0])

                _res = client.q(detection_sql)
                anomaly_rows = _res or []

            for a in anomaly_rows:
                (src, cp, period, ind_code, currency, svc_class,
                 obs_val, base_avg, base_cnt, ratio) = a

                ratio_f   = float(ratio or 0)
                obs_f     = float(obs_val or 0)
                base_f    = float(base_avg or 0)
                severity  = _severity_for(ratio_f)
                vid       = _anomaly_vid(run_id, fc, str(src or ""), str(cp or ""), str(period or ""))
                anomaly_id = f"{src}:{cp}:{period}"

                if True:

                    client = get_kotoba_client()
                    _res = client.q(
                        "INSERT INTO vertex_resource_flow_anomaly "
                        "(vertex_id, anomaly_id, flow_class, source_did, counterparty_did, "
                        "fiscal_period, industry_code, currency, service_class, "
                        "observed_value, baseline_avg, baseline_window_days, "
                        "baseline_sample_count, threshold_factor, severity, "
                        "observed_at, detection_run_id, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            vid, anomaly_id, fc,
                            str(src or ""),
                            str(cp or "") if cp != "independent" else None,
                            str(period or ""),
                            str(ind_code or "") or None,
                            str(currency or "") or None,
                            str(svc_class or "") or None,
                            obs_f, base_f, window_days,
                            int(base_cnt or 0), threshold, severity,
                            observed_at, run_id, observed_at,
                        ),
                    )
                total_flagged += 1

                if post and severity in ("high", "critical"):
                    _emit_anomaly_post(
                        fc, str(src or ""), str(cp or ""), str(period or ""),
                        obs_f, base_f, ratio_f, severity, window_days, int(base_cnt or 0),
                    )

        except Exception as e:  # noqa: BLE001
            LOG.error("detect anomaly failed for fc=%s run=%s: %s", fc, run_id, e)

    LOG.info("detect.anomaly done: run=%s scanned=%d flagged=%d", run_id, total_scanned, total_flagged)
    return {"runId": run_id, "scanned": total_scanned, "flagged": total_flagged}


def task_resource_flow_project_flow(
    flowClass: str = "",
    recordUri: str = "",
    observedAt: str = "",
    record: dict[str, Any] | None = None,
    primaryDid: str = _PRIMARY_DID,
    orgId: str = "anon",
    userId: str = "anon",
    **kwargs: Any,
) -> dict[str, Any]:
    """Project one legal-entity flow record into vertex_resource_flow_*.

    BPMN: resource_flow_project_flow.
    Task type: resource-flow.project.flow.
    """
    flow_class = _str(flowClass)
    table = _FLOW_TABLES.get(flow_class)
    if not table or not recordUri:
        return {"error": "InvalidRecord", "message": "flowClass + recordUri required"}

    rec = record if isinstance(record, dict) else {}
    rejected = _reject_individual(rec)
    if rejected:
        return {"flowClass": flow_class, "vertexId": "", "status": "rejected", "rejectReason": rejected}

    source_did = _str(rec.get("sourceDid"))
    if not source_did:
        return {"error": "InvalidRecord", "message": "sourceDid required"}

    vid = _flow_vid(flow_class, recordUri)
    now = _now_iso()
    observed = observedAt or now
    owner = primaryDid or _PRIMARY_DID
    emitter_root = _str(rec.get("sourceRootDid")) or None
    cp_root = _str(rec.get("counterpartyRootDid")) or None
    common = {
        "vertex_id": vid,
        "sensitivity_ord": 1,
        "owner_did": owner,
        "source_did": source_did,
        "counterparty_did": _str(rec.get("counterpartyDid")) or None,
        "fiscal_period": _str(rec.get("fiscalPeriod")),
        "industry_code": _str(rec.get("industryCode")),
        "cohort_id": _str(rec.get("cohortId")) or None,
        "cohort_size": _int_or_none(rec.get("cohortSize")),
        "source_url": _str(rec.get("sourceUrl")),
        "source_license": _str(rec.get("sourceLicense")),
        "note": _str(rec.get("note")),
        "record_uri": recordUri,
        "observed_at": observed,
        "created_at": now,
        "org_id": orgId or "anon",
        "user_id": userId or "anon",
        "actor_id": owner,
        "facade_did": source_did,
        "facade_did_hash": _facade_hash(source_did),
        "identity_method": _identity_method(source_did),
        "root_did": emitter_root,
        "root_did_hash": _facade_hash(emitter_root or "") if emitter_root else None,
        "root_identity_addr": None,
        "migration_status": "linked" if emitter_root else "facade-only",
        "counterparty_root_did": cp_root,
        "counterparty_root_did_hash": _facade_hash(cp_root or "") if cp_root else None,
    }

    if True:

        client = get_kotoba_client()
        _res = client.q(f"SELECT vertex_id FROM {table} WHERE vertex_id = %s LIMIT 1", (vid,))
        if (_res[0] if _res else None):
            return {"flowClass": flow_class, "vertexId": vid, "status": "duplicate"}

        if flow_class == "currency":
            row = {
                **common,
                "flow_type": _str(rec.get("flowType")),
                "amount": _num(rec.get("amount"), 0),
                "amount_bucket": _str(rec.get("amountBucket")),
                "currency": _str(rec.get("currency")),
            }
        elif flow_class == "service":
            row = {
                **common,
                "service_class": _str(rec.get("serviceClass")),
                "service_count": int(_num(rec.get("count"), 0) or 0),
                "service_unit": _str(rec.get("unit")),
                "revenue": _num(rec.get("revenue"), None),
                "revenue_currency": _str(rec.get("revenueCurrency")) or None,
            }
        else:
            row = {
                **common,
                "flow_type": _str(rec.get("flowType")),
                "headcount_delta": int(_num(rec.get("headcountDelta"), 0) or 0),
            }

        cols = list(row.keys())
        _res = client.q(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
            tuple(row[c] for c in cols),
        )
    return {"flowClass": flow_class, "vertexId": vid, "status": "projected"}


def task_resource_flow_get_sankey(
    flowClass: str = "",
    sourceDid: str = "",
    fiscalPeriod: str = "",
    industryCode: str = "",
    domain: str = "",
    limit: Any = 200,
    **kwargs: Any,
) -> dict[str, Any]:
    flow_class = _str(flowClass)
    mv = _SANKEY_TABLES.get(flow_class)
    if not mv:
        return {"error": "InvalidRequest", "message": "flowClass must be currency / service / personnel"}

    clauses: list[str] = []
    params: list[Any] = []
    if sourceDid:
        clauses.append("source_did = %s")
        params.append(sourceDid)
    if fiscalPeriod:
        clauses.append("fiscal_period = %s")
        params.append(fiscalPeriod)
    if industryCode:
        clauses.append("industry_code = %s")
        params.append(industryCode)
    elif domain and domain in _DOMAIN_INDUSTRY:
        codes = _DOMAIN_INDUSTRY[domain]
        clauses.append(f"industry_code IN ({', '.join(['%s'] * len(codes))})")
        params.extend(codes)

    limit_n = _bounded_int(limit, 200, 1, 1000)
    sql = f"SELECT * FROM {mv}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" LIMIT {limit_n}"

    if True:

        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        rows = _rows_as_dicts(cur, _res)

    nodes = sorted({
        str(v)
        for row in rows
        for v in (row.get("source_did"), row.get("counterparty_did"))
        if v
    })
    return {"flowClass": flow_class, "edges": rows, "nodes": [{"id": n} for n in nodes]}


def task_resource_flow_get_actor_labels(dids: Any = None, **kwargs: Any) -> dict[str, Any]:
    raw: list[str] = []
    if isinstance(dids, list):
        raw = [str(v) for v in dids]
    elif isinstance(dids, str):
        raw = dids.split(",")
    values = list(dict.fromkeys([v.strip() for v in raw if v.strip()]))[:256]
    if not values:
        return {"error": "InvalidRequest", "message": "dids required"}

    sql = (
        "SELECT * FROM view_resource_flow_actor_label "
        f"WHERE did IN ({', '.join(['%s'] * len(values))})"
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(values))
        rows = _rows_as_dicts(cur, _res)

    by_did: dict[str, dict[str, Any]] = {}
    for row in rows:
        d = str(row.get("did") or "")
        if not d:
            continue
        cur = by_did.get(d)
        if cur is None or (row.get("display_name") is not None and cur.get("display_name") is None):
            by_did[d] = row

    labels = []
    for d in values:
        row = by_did.get(d)
        if not row:
            labels.append({"did": d})
            continue
        labels.append({
            "did": d,
            "kind": row.get("kind"),
            "facadeDid": row.get("facade_did"),
            "rootDid": row.get("root_did"),
            "handle": row.get("handle"),
            "displayName": row.get("display_name"),
            "description": row.get("description"),
            "rootIdentityAddr": row.get("root_identity_addr"),
        })
    return {"labels": labels}


def task_resource_flow_list_flows(
    flowClass: str = "",
    sourceDid: str = "",
    fiscalPeriod: str = "",
    limit: Any = 50,
    offset: Any = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    flow_class = _str(flowClass)
    table = _FLOW_TABLES.get(flow_class)
    if not table:
        return {"error": "InvalidRequest", "message": "flowClass must be currency / service / personnel"}

    clauses: list[str] = []
    params: list[Any] = []
    if sourceDid:
        clauses.append("source_did = %s")
        params.append(sourceDid)
    if fiscalPeriod:
        clauses.append("fiscal_period = %s")
        params.append(fiscalPeriod)
    limit_n = _bounded_int(limit, 50, 1, 500)
    offset_n = _bounded_int(offset, 0, 0, 100_000)

    sql = f"SELECT * FROM {table}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" LIMIT {limit_n} OFFSET {offset_n}"
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        rows = _rows_as_dicts(cur, _res)
    return {"flowClass": flow_class, "flows": rows, "total": len(rows), "offset": offset_n, "limit": limit_n}


def task_resource_flow_list_anomalies(
    flowClass: str = "",
    severity: str = "",
    sourceDid: str = "",
    fiscalPeriod: str = "",
    since: str = "",
    reviewed: str = "open",
    limit: Any = 50,
    offset: Any = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    limit_n = _bounded_int(limit, 50, 1, 200)
    offset_n = _bounded_int(offset, 0, 0, 100_000)
    reviewed_v = reviewed if reviewed in ("open", "closed", "any") else "open"

    clauses: list[str] = []
    params: list[Any] = []
    if flowClass:
        clauses.append("a.flow_class = %s")
        params.append(flowClass)
    if severity:
        clauses.append("a.severity = %s")
        params.append(severity)
    if sourceDid:
        clauses.append("a.source_did = %s")
        params.append(sourceDid)
    if fiscalPeriod:
        clauses.append("a.fiscal_period = %s")
        params.append(fiscalPeriod)
    if since:
        clauses.append("a.observed_at >= %s")
        params.append(since)
    if reviewed_v == "open":
        clauses.append("rl.review_count IS NULL")
    elif reviewed_v == "closed":
        clauses.append("rl.review_count IS NOT NULL")

    sql = """
        SELECT
          a.vertex_id, a.anomaly_id, a.flow_class, a.source_did, a.counterparty_did,
          a.fiscal_period, a.industry_code, a.currency, a.service_class,
          a.observed_value, a.baseline_avg, a.baseline_window_days, a.baseline_sample_count,
          a.threshold_factor, a.severity, a.observed_at, a.detection_run_id, a.post_uri,
          rl.review_count AS review_count,
          rl.latest_observed_at AS last_reviewed_at,
          rv.action AS last_action,
          rv.reviewer_did AS last_reviewer_did,
          rv.thread_post_uri AS last_thread_post_uri
        FROM vertex_resource_flow_anomaly a
        LEFT JOIN mv_resource_flow_anomaly_review_latest rl ON rl.anomaly_id = a.vertex_id
        LEFT JOIN vertex_resource_flow_anomaly_review rv
          ON rv.anomaly_id = rl.anomaly_id AND rv.observed_at = rl.latest_observed_at
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY a.observed_at DESC LIMIT {limit_n} OFFSET {offset_n}"
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, tuple(params))
        rows = _rows_as_dicts(cur, _res)
    return {"anomalies": rows, "total": len(rows), "offset": offset_n, "limit": limit_n, "reviewed": reviewed_v}


def task_resource_flow_review_anomaly(
    anomalyId: str = "",
    action: str = "",
    reason: str = "",
    reviewerDid: str = "",
    primaryDid: str = _PRIMARY_DID,
    orgId: str = "anon",
    userId: str = "anon",
    **kwargs: Any,
) -> dict[str, Any]:
    """Append one review action to vertex_resource_flow_anomaly_review."""
    if not anomalyId:
        return {"error": "InvalidRequest", "message": "anomalyId required"}
    if action not in _ANOMALY_ACTIONS:
        return {"error": "InvalidAction", "message": "action must be one of acknowledge/dismiss/escalate"}

    if True:

        client = get_kotoba_client()
        _res = client.q(f"SELECT vertex_id FROM {_ANOMALY_TABLE} WHERE vertex_id = %s LIMIT 1", (anomalyId,))
        if not (_res[0] if _res else None):
            return {"error": "AnomalyNotFound", "message": anomalyId}

        review_id = _review_id()
        vid = _review_vid(review_id)
        now = _now_iso()
        owner = primaryDid or _PRIMARY_DID
        caller = reviewerDid or owner
        _res = client.q(
            f"INSERT INTO {_ANOMALY_REVIEW_TABLE} "
            "(vertex_id, sensitivity_ord, owner_did, review_id, anomaly_id, action, "
            "reason, reviewer_did, reviewer_facade, thread_post_uri, observed_at, "
            "created_at, org_id, user_id, actor_id, root_did, root_did_hash, "
            "root_identity_addr, facade_did, facade_did_hash, identity_method, migration_status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                vid, 1, owner, review_id, anomalyId, action,
                reason or None, caller, caller, None, now,
                now, orgId or "anon", userId or "anon", owner,
                None, None, None, owner, _facade_hash(owner), _identity_method(owner), "facade-only",
            ),
        )
    return {"reviewId": review_id, "anomalyId": anomalyId, "action": action, "vertexId": vid}


def register(worker: Any, *, timeout_ms: int = 120_000) -> None:
    """Wire resource-flow primitives onto the shared LangServer worker."""
    worker.task(
        task_type="resource-flow.detect.anomaly",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_resource_flow_detect_anomaly)
    worker.task(
        task_type="resource-flow.project.flow",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_resource_flow_project_flow)
    worker.task(
        task_type="resource-flow.review.anomaly",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_resource_flow_review_anomaly)
    worker.task(
        task_type="resource-flow.get.sankey",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_resource_flow_get_sankey)
    worker.task(
        task_type="resource-flow.get.actor-labels",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_resource_flow_get_actor_labels)
    worker.task(
        task_type="resource-flow.list.flows",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_resource_flow_list_flows)
    worker.task(
        task_type="resource-flow.list.anomalies",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_resource_flow_list_anomalies)
