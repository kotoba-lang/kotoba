"""kyber `bmc_iteration` graph — lean Build-Measure-Learn loop.

Runs inside the lg-kyber pod (mitama-udf namespace). State machine:

    bootstrap → load_bmc_state → pick_hypothesis → measure → evaluate
                                                              ↓
                                                            decide
                                                              ↓
                                                          update_bmc → END

Measurement dispatchers (metric_query prefix):

  sql:vertex_kyber_oss_download_count[:Nd]
  sql:vertex_kyber_tenant_count_by_tier:{tier}
  sql:vertex_kyber_billing_event_sum:{metric}:{Nd|Nh}
  sql:vertex_kyber_github_star_count[:Nd]
  sql:vertex_kyber_lead_count_by_status:{status}
  sql:vertex_kyber_employee_count
  external:stripe_subscriptions[:filter]
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from lg_kyber.db import fetch as pg_fetch, fetchval as pg_fetchval
from . import _llm  # type: ignore[attr-defined]

_log = logging.getLogger(__name__)

DecisionLiteral = Literal["persevere", "pivot", "kill", "extend"]

_WINDOW_RE = re.compile(r"^(\d+)([smhd])$")


def _parse_window_ms(s: str) -> int:
    m = _WINDOW_RE.match(s or "")
    if not m:
        return 30 * 86400 * 1000
    n = int(m.group(1))
    unit = m.group(2)
    return n * {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}[unit]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _State(TypedDict, total=False):
    # Inputs
    org_did: str
    actor_did: str
    trigger: str
    dry_run: bool
    forced_hypothesis_slug: str

    # Identity
    iteration_id: str
    started_at_iso: str
    started_at_ms: int

    # BMC head (in-memory; kyber uses vertex_kyber_bmc_* if available, else skips)
    bmc_version_in: int
    canvas: dict[str, Any]

    # Picked hypothesis (loaded from vertex_kyber_bmc_hypothesis)
    hyp_slug: str
    hyp_block: str
    hyp_statement: str
    hyp_metric: str
    hyp_metric_query: str
    hyp_threshold: float
    hyp_baseline: float
    hyp_deadline_iso: str
    hyp_min_sample: int
    hyp_auto_apply_pivot: bool
    iteration_no: int

    # Measurement
    measured_value: float
    sample_size: int
    measurement_source: str
    measurement_error: str
    measurement_window_start_ms: int
    measurement_window_end_ms: int
    measurement_raw: str
    measurement_latency_ms: int

    # Evaluation
    passed: bool
    deadline_reached: bool
    min_sample_reached: bool

    # Decision
    decision: DecisionLiteral
    decision_rationale: str
    authored_by: str
    proposed_block_edits: dict[str, Any]

    # Outputs
    bmc_version_out: int
    notes: str
    idle: bool
    picked_out: dict[str, Any] | None
    measurement_out: dict[str, Any] | None
    evaluation_out: dict[str, Any] | None
    decision_out: dict[str, Any] | None


async def _bootstrap(state: _State) -> _State:
    return {
        "iteration_id": uuid.uuid4().hex,
        "started_at_iso": _now_iso(),
        "started_at_ms": int(time.time() * 1000),
        "authored_by": "agent:lg-kyber-bmc",
        "idle": False,
        "passed": False,
        "deadline_reached": False,
        "min_sample_reached": False,
        "org_did": state.get("org_did") or "did:web:kyber.etzhayyim.com",
        "actor_did": state.get("actor_did") or "agent:lg-kyber-bmc",
    }


async def _load_bmc_state(state: _State) -> _State:
    try:
        row = await pg_fetchval(
            """
            SELECT canvas_json FROM vertex_kyber_bmc_state
            ORDER BY version DESC LIMIT 1
            """
        )
        if row:
            try:
                canvas = json.loads(row)
            except Exception:
                canvas = {}
            return {"bmc_version_in": 1, "canvas": canvas}
    except Exception as e:
        _log.debug("[kyber.bmc] load_bmc_state skipped: %s", e)
    return {"bmc_version_in": 0, "canvas": {}}


async def _pick_hypothesis(state: _State) -> _State:
    try:
        row = await pg_fetchval(
            """
            SELECT slug FROM vertex_kyber_bmc_hypothesis
            WHERE status = 'active'
            ORDER BY created_at ASC LIMIT 1
            """
        )
        if not row:
            return {"idle": True, "notes": "no active kyber hypothesis; loop idle"}
        slug = str(row)
        full = await pg_fetchval(
            "SELECT row_to_json(h) FROM vertex_kyber_bmc_hypothesis h WHERE slug = $1",
            slug,
        )
        if not full:
            return {"idle": True, "notes": f"hypothesis {slug} not found"}
        h = json.loads(full) if isinstance(full, str) else dict(full)
        iter_no = (
            await pg_fetchval(
                "SELECT COUNT(*) FROM vertex_kyber_bmc_iteration WHERE hypothesis_slug = $1",
                slug,
            )
            or 0
        ) + 1
        return {
            "idle": False,
            "hyp_slug": h.get("slug", slug),
            "hyp_block": h.get("block", ""),
            "hyp_statement": h.get("statement", ""),
            "hyp_metric": h.get("metric", ""),
            "hyp_metric_query": h.get("metric_query", ""),
            "hyp_threshold": float(h.get("threshold", 0)),
            "hyp_baseline": float(h.get("baseline", 0)),
            "hyp_deadline_iso": h.get("deadline_iso", ""),
            "hyp_min_sample": int(h.get("min_sample", 0)),
            "hyp_auto_apply_pivot": bool(h.get("auto_apply_pivot", False)),
            "iteration_no": int(iter_no),
            "picked_out": {"slug": slug, "block": h.get("block"), "iterationNo": int(iter_no)},
        }
    except Exception as e:
        _log.debug("[kyber.bmc] pick_hypothesis DB unavailable: %s — using idle", e)
        return {"idle": True, "notes": f"DB unavailable: {e}"}


async def _measure(state: _State) -> _State:
    if state.get("idle"):
        return {}
    mq = state.get("hyp_metric_query", "")
    prefix = mq.split(":", 1)[0] if mq else ""
    t0 = time.time()
    if prefix == "sql":
        out = await _measure_sql(mq)
    elif prefix == "external" and mq.startswith("external:stripe"):
        out = await _measure_stripe(mq)
    else:
        out = {
            "value": 0.0, "sample": 0, "source": "unknown-prefix",
            "error": f"unsupported metric_query prefix: {prefix or '(empty)'}",
            "window_start_ms": 0, "window_end_ms": 0, "raw": "",
        }
    latency = int((time.time() - t0) * 1000)
    return {
        "measured_value": float(out["value"]),
        "sample_size": int(out["sample"]),
        "measurement_source": str(out["source"]),
        "measurement_error": str(out.get("error") or ""),
        "measurement_window_start_ms": int(out.get("window_start_ms") or 0),
        "measurement_window_end_ms": int(out.get("window_end_ms") or 0),
        "measurement_raw": str(out.get("raw") or "")[:4096],
        "measurement_latency_ms": latency,
        "measurement_out": {
            "value": repr(float(out["value"])),
            "sample": int(out["sample"]),
            "source": str(out["source"]),
            "error": str(out.get("error") or ""),
        },
    }


async def _measure_sql(metric_query: str) -> dict[str, Any]:
    parts = metric_query.split(":")
    dispatcher = parts[1] if len(parts) > 1 else ""
    arg1 = parts[2] if len(parts) > 2 else ""
    arg2 = parts[3] if len(parts) > 3 else ""
    now_ms = int(time.time() * 1000)
    window_ms = _parse_window_ms(arg2 or arg1 or "30d")
    since_ms = now_ms - window_ms
    since_iso = datetime.fromtimestamp(since_ms / 1000.0, tz=timezone.utc).isoformat()

    try:
        if dispatcher == "vertex_kyber_oss_download_count":
            c = await pg_fetchval(
                """
                SELECT COUNT(*) FROM vertex_kyber_oss_event
                WHERE event_type = 'download' AND created_at >= $1
                """,
                since_iso,
            )
            return {
                "value": float(c or 0), "sample": int(c or 0),
                "source": f"vertex_kyber_oss_event.download_count since={since_iso}",
                "window_start_ms": since_ms, "window_end_ms": now_ms, "raw": "",
            }
        if dispatcher == "vertex_kyber_github_star_count":
            c = await pg_fetchval(
                """
                SELECT COUNT(*) FROM vertex_kyber_oss_event
                WHERE event_type = 'star' AND created_at >= $1
                """,
                since_iso,
            )
            return {
                "value": float(c or 0), "sample": int(c or 0),
                "source": f"vertex_kyber_oss_event.star_count since={since_iso}",
                "window_start_ms": since_ms, "window_end_ms": now_ms, "raw": "",
            }
        if dispatcher == "vertex_kyber_tenant_count_by_tier":
            tier = arg1 or "starter"
            c = await pg_fetchval(
                "SELECT COUNT(*) FROM vertex_kyber_tenant WHERE tier = $1 AND status = 'active'",
                tier,
            )
            return {
                "value": float(c or 0), "sample": int(c or 0),
                "source": f"vertex_kyber_tenant.count tier={tier}",
                "window_start_ms": 0, "window_end_ms": now_ms, "raw": "",
            }
        if dispatcher == "vertex_kyber_billing_event_sum":
            metric = arg1 or "mrr_jpy"
            row = await pg_fetch(
                """
                SELECT COALESCE(SUM(qty), 0) AS s, COUNT(*) AS c
                FROM vertex_kyber_billing_event
                WHERE metric = $1 AND ts_ms >= $2
                """,
                metric, since_ms,
            )
            r = row[0] if row else {"s": 0, "c": 0}
            return {
                "value": float(r["s"] or 0), "sample": int(r["c"] or 0),
                "source": f"vertex_kyber_billing_event.sum metric={metric} since={since_iso}",
                "window_start_ms": since_ms, "window_end_ms": now_ms, "raw": "",
            }
        if dispatcher == "vertex_kyber_lead_count_by_status":
            status = arg1 or "new"
            c = await pg_fetchval(
                "SELECT COUNT(*) FROM vertex_kyber_lead WHERE outreach_status = $1", status,
            )
            return {
                "value": float(c or 0), "sample": int(c or 0),
                "source": f"vertex_kyber_lead.count status={status}",
                "window_start_ms": 0, "window_end_ms": now_ms, "raw": "",
            }
        if dispatcher == "vertex_kyber_employee_count":
            c = await pg_fetchval(
                "SELECT COUNT(*) FROM vertex_kyber_employee WHERE status = 'active'",
            )
            return {
                "value": float(c or 0), "sample": int(c or 0),
                "source": "vertex_kyber_employee.active_count",
                "window_start_ms": 0, "window_end_ms": now_ms, "raw": "",
            }
    except Exception as e:
        _log.exception("[kyber.bmc.measure_sql] dispatcher=%s failed", dispatcher)
        return {
            "value": 0.0, "sample": 0, "source": "sql-error",
            "error": str(e)[:200],
            "window_start_ms": since_ms, "window_end_ms": now_ms, "raw": "",
        }
    return {
        "value": 0.0, "sample": 0, "source": "unknown-dispatcher",
        "error": f"unknown sql dispatcher: {dispatcher!r}",
        "window_start_ms": since_ms, "window_end_ms": now_ms, "raw": "",
    }


async def _measure_stripe(metric_query: str) -> dict[str, Any]:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        return {
            "value": 0.0, "sample": 0, "source": "stripe-key-missing",
            "error": "STRIPE_SECRET_KEY not set",
            "window_start_ms": 0, "window_end_ms": int(time.time() * 1000), "raw": "",
        }
    parts = metric_query.split(":")
    filt = parts[2] if len(parts) > 2 else "active"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                "https://api.stripe.com/v1/subscriptions",
                params={"limit": 100, "status": filt},
                headers={"authorization": f"Bearer {key}"},
            )
        if r.status_code != 200:
            return {
                "value": 0.0, "sample": 0, "source": "stripe-http-error",
                "error": f"HTTP {r.status_code}",
                "window_start_ms": 0, "window_end_ms": int(time.time() * 1000),
                "raw": r.text[:512],
            }
        data = r.json()
        items = data.get("data", []) or []
        return {
            "value": float(len(items)), "sample": len(items),
            "source": f"stripe subscriptions(status={filt})",
            "window_start_ms": 0, "window_end_ms": int(time.time() * 1000),
            "raw": json.dumps({"count": len(items), "has_more": data.get("has_more", False)})[:512],
        }
    except Exception as e:
        _log.exception("[kyber.bmc.measure_stripe] failed")
        return {
            "value": 0.0, "sample": 0, "source": "stripe-throw",
            "error": str(e)[:200],
            "window_start_ms": 0, "window_end_ms": int(time.time() * 1000), "raw": "",
        }


def _evaluate(state: _State) -> _State:
    if state.get("idle"):
        return {}
    threshold = float(state.get("hyp_threshold", 0.0))
    measured = float(state.get("measured_value", 0.0))
    deadline_iso = state.get("hyp_deadline_iso", "")
    min_sample = int(state.get("hyp_min_sample", 0))
    sample = int(state.get("sample_size", 0))
    passed = measured >= threshold
    deadline_reached = False
    if deadline_iso:
        try:
            dl = datetime.fromisoformat(deadline_iso.replace("Z", "+00:00"))
            deadline_reached = datetime.now(tz=timezone.utc) >= dl
        except Exception:
            pass
    min_sample_reached = sample >= min_sample
    return {
        "passed": passed,
        "deadline_reached": deadline_reached,
        "min_sample_reached": min_sample_reached,
        "evaluation_out": {
            "passed": passed,
            "deadlineReached": deadline_reached,
            "minSampleReached": min_sample_reached,
        },
    }


def _decide_deterministic(state: _State) -> tuple[DecisionLiteral, str]:
    passed = bool(state.get("passed"))
    deadline = bool(state.get("deadline_reached"))
    min_sample = bool(state.get("min_sample_reached"))
    measured = state.get("measured_value", 0)
    threshold = state.get("hyp_threshold", 0)
    sample = state.get("sample_size", 0)
    min_n = state.get("hyp_min_sample", 0)
    iter_no = state.get("iteration_no", 1)
    if passed and min_sample:
        return "persevere", (
            f"measured={measured} >= threshold={threshold} with "
            f"sample={sample} (>= min {min_n}). Iteration #{iter_no} — promote BMC."
        )
    if not passed and deadline:
        action: DecisionLiteral = "kill" if iter_no >= 3 else "pivot"
        return action, (
            f"deadline reached; measured={measured} < threshold={threshold} "
            f"after {iter_no} iteration(s). "
            + ("Recommend kill — hypothesis exhausted." if action == "kill"
               else "Recommend pivot — propose BMC block edit.")
        )
    if not min_sample:
        return "extend", f"sample={sample} < min {min_n}; not enough signal yet."
    return "extend", (
        f"measured={measured} < threshold={threshold} but deadline not "
        f"reached — extending iteration window."
    )


async def _decide(state: _State) -> _State:
    if state.get("idle"):
        return {}
    action, rationale = _decide_deterministic(state)
    proposed: dict[str, Any] = {}

    system_prompt = (
        "You are the resident BMC iteration agent for kyber.etzhayyim.com (ERP SaaS for Japan SMB).\n"
        "Return a SINGLE JSON object: { action, rationale, proposed_block_edits? }.\n"
        "action ∈ {persevere, pivot, kill, extend}. On pivot, include proposed_block_edits "
        "with concrete add_bullets (≤3, ≤200 chars each, Japanese OK).\n"
        "Output ONLY JSON."
    )
    user_prompt = json.dumps({
        "hypothesis": {
            "slug": state.get("hyp_slug"),
            "block": state.get("hyp_block"),
            "statement": state.get("hyp_statement"),
            "threshold": state.get("hyp_threshold"),
            "deadline_iso": state.get("hyp_deadline_iso"),
        },
        "measurement": {
            "value": state.get("measured_value"),
            "sample": state.get("sample_size"),
            "source": state.get("measurement_source"),
            "error": state.get("measurement_error"),
        },
        "flags": {
            "passed": state.get("passed"),
            "deadline_reached": state.get("deadline_reached"),
            "iteration_no": state.get("iteration_no"),
        },
        "deterministic_hint": {"action": action, "rationale": rationale},
    }, ensure_ascii=False)

    parsed, source = _llm.call_llm_json(
        f"{system_prompt}\n\n{user_prompt}", max_tokens=400,
    )
    authored_by = "agent:lg-kyber-bmc"
    if parsed and isinstance(parsed, dict) and parsed.get("action") in ("persevere", "pivot", "kill", "extend"):
        action = parsed["action"]  # type: ignore[assignment]
        rationale = str(parsed.get("rationale") or rationale)[:1000]
        authored_by = f"agent:llm-{source}"
        pe = parsed.get("proposed_block_edits") or {}
        if isinstance(pe, dict) and pe.get("block"):
            bullets = pe.get("add_bullets") or []
            if isinstance(bullets, list):
                proposed = {
                    "block": str(pe["block"])[:64],
                    "addBullets": [str(b)[:280] for b in bullets[:3]],
                }

    return {
        "decision": action,
        "decision_rationale": rationale,
        "authored_by": authored_by,
        "proposed_block_edits": proposed,
        "decision_out": {
            "action": action,
            "rationale": rationale,
            "authoredBy": authored_by,
            "proposedBlockEdits": proposed,
        },
    }


async def _update_bmc(state: _State) -> _State:
    if state.get("idle"):
        return {"notes": "idle"}
    if state.get("dry_run"):
        return {"notes": "dry-run; skipped persistence"}

    action = state.get("decision", "extend")
    notes = (
        f"kyber BMC · {state.get('hyp_slug', '?')} · "
        f"iter #{state.get('iteration_no', 1)} · {action} "
        f"(by {state.get('authored_by', 'agent:lg-kyber-bmc')})"
    )
    try:
        from lg_kyber.db import execute
        await execute(
            """
            INSERT INTO vertex_kyber_bmc_iteration
              (iteration_id, hypothesis_slug, iteration_no, measured_value,
               measurement_source, passed, decision, decision_rationale,
               authored_by, org_did, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            """,
            state.get("iteration_id", uuid.uuid4().hex),
            state.get("hyp_slug", ""),
            state.get("iteration_no", 1),
            float(state.get("measured_value", 0)),
            state.get("measurement_source", "unknown"),
            bool(state.get("passed")),
            action,
            state.get("decision_rationale", "")[:2048],
            state.get("authored_by", "agent:lg-kyber-bmc"),
            state.get("org_did", "did:web:kyber.etzhayyim.com"),
            datetime.now(timezone.utc),
        )
    except Exception as e:
        _log.warning("[kyber.bmc] update_bmc insert failed (table may not exist yet): %s", e)
        notes += " [persistence skipped]"

    return {"notes": notes, "bmc_version_out": state.get("bmc_version_in", 0)}


def _maybe_idle(state: _State) -> str:
    return END if state.get("idle") else "measure"


_g: StateGraph = StateGraph(_State)
_g.add_node("bootstrap", _bootstrap)
_g.add_node("load_bmc_state", _load_bmc_state)
_g.add_node("pick_hypothesis", _pick_hypothesis)
_g.add_node("measure", _measure)
_g.add_node("evaluate", _evaluate)
_g.add_node("decide", _decide)
_g.add_node("update_bmc", _update_bmc)

_g.add_edge(START, "bootstrap")
_g.add_edge("bootstrap", "load_bmc_state")
_g.add_edge("load_bmc_state", "pick_hypothesis")
_g.add_conditional_edges("pick_hypothesis", _maybe_idle, {"measure": "measure", END: END})
_g.add_edge("measure", "evaluate")
_g.add_edge("evaluate", "decide")
_g.add_edge("decide", "update_bmc")
_g.add_edge("update_bmc", END)

GRAPH = _g.compile()
