"""etzhayyim Artificial Organism — 30-minute master routine.

Maximizes: Ω(t) = Shannon_η(t) × U_total(t)

  Shannon_η = autonomous decisions executed / all decisions needed
            ≈ (agent_runs_without_human_gate / total_decisions_possible)

  U_total   = min(U_spirit, U_wellbecoming, U_feeling, U_buffer)
  Floor     : if any axis = 0 → U_total = 0 (spirit zero kills utility — Axiom 4)

Org axis mapping:
  Spirit      → OKR attainment + CEO strategic clarity + Shannon η
  Wellbecoming→ delivery quality + team growth + active projects
  Feeling     → team morale proxy (pending task pressure) + legal case load
  Buffer      → financial runway (months) + infra health score

Decision routing (from evaluate_objective):
  critical_alert    → create priority=1 human task for responsible agent
  okr_drift         → CEO task (strategy review)
  legal_urgent      → CLO task (case sweep)
  budget_pressure   → CEO+COO task (financial review)
  infra_anomaly     → Eng infra task
  deploy_anomaly    → Eng deploy task
  agent_silent      → COO task (ops anomaly)
  wellbecoming_risk → wellbecoming proactive connect (Zeebe message)
  floor_violated    → wellbecoming floor alert (Zeebe message)

Pyzeebe task types:
  kaisya.master.collectState       — parallel DB collection of org state
  kaisya.master.evaluateObjective  — LangGraph Ω(t) + decision routing
  kaisya.master.executeDecisions   — dispatch tasks + Zeebe messages
  kaisya.master.writeSnapshot      — persist vertex_kaisya_org_snapshot
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import datetime as _dt
import json
import logging
import os
import uuid
from typing import Any, TypedDict

from kotodama.primitives import langgraph_registry

LOG = logging.getLogger("kaisya.master")

OWNER_DID  = "did:web:bpmn.etzhayyim.com"
ORG_DID    = "did:web:kaisya.etzhayyim.com"

# ADR-2605010000: RunPod 6000 Ada is LLM SSoT. Murakumo removed from LLM path.
# llm.call_tier() routes via _etzhayyim_LLM_URL → murakumo/RunPod per env config.

# Threshold below which we flag a decision as requiring human gate
OMEGA_ALERT_THRESHOLD: float = float(os.environ.get("KAISYA_OMEGA_ALERT", "0.5"))
ETA_MIN_THRESHOLD: float      = float(os.environ.get("KAISYA_ETA_MIN", "0.6"))

# P8: Teams floor alert — ADR-2604282300: com.etzhayyim.* must NOT call CF Worker directly.
# Routes through bpmn-dispatcher ClusterIP; fails gracefully until BPMN binding for
# com.etzhayyim.apps.microsoft.sendMail is seeded (see deps.toml [[migrations]] kaisya-microsoft-bpmn-binding).
MICROSOFT_XRPC_URL: str = os.environ.get(
    "MICROSOFT_XRPC_URL",
    os.environ.get(
        "BPMN_DISPATCHER_INTERNAL_URL",
        "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080",
    ),
)
MICROSOFT_API_KEY: str  = os.environ.get("SS_MICROSOFT_API_KEY", "")
KAISYA_ALERT_TO: str    = os.environ.get("KAISYA_ALERT_TO", "j.kawasaki@etzhayyim.com")

# ── Helpers ───────────────────────────────────────────────────────────

def _now_iso() -> str:
    # RisingWave TIMESTAMP (without timezone) rejects Z/+00:00 suffix.
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")

def _vertex_id(kind: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://{OWNER_DID}/com.etzhayyim.apps.kaisya.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"

def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _llm_complete_sync(prompt: str, max_tokens: int = 600) -> str:
    """Single-turn LLM via llm.call_tier (ADR-2605010000 — RunPod 6000 Ada SSoT)."""
    try:
        from kotodama.llm import call_tier
        result = call_tier("structured", system="", user=prompt, max_tokens=max_tokens)
        return str(result.get("content", "")).strip() or "[empty]"
    except Exception as exc:
        LOG.warning("LLM unavailable: %s", exc)
        return f"[LLM unavailable: {exc}]"


async def _llm_complete(prompt: str, max_tokens: int = 600) -> str:
    """Async wrapper — call_tier is sync, run in thread executor."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _llm_complete_sync, prompt, max_tokens)


async def _send_floor_alert(omega: float, floor_violated: bool, synthesis_text: str) -> None:
    reason = "floor violation (axis = 0)" if floor_violated else f"Ω = {omega:.3f} < {OMEGA_ALERT_THRESHOLD}"
    body_html = (
        f"<h2>Kaisya Well-Becoming Alert</h2>"
        f"<p><strong>Reason:</strong> {reason}</p>"
        f"<p><strong>Omega:</strong> {omega:.3f}</p>"
        f"<p><strong>Floor violated:</strong> {floor_violated}</p>"
        f"<pre>{synthesis_text[:2000]}</pre>"
    )
    try:
        import httpx  # type: ignore
        headers: dict[str, str] = {"content-type": "application/json"}
        if MICROSOFT_API_KEY:
            headers["authorization"] = f"Bearer {MICROSOFT_API_KEY}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{MICROSOFT_XRPC_URL}/xrpc/com.etzhayyim.apps.microsoft.sendMail",
                json={
                    "to": [KAISYA_ALERT_TO],
                    "subject": f"[Kaisya Alert] Ω={omega:.3f} — {reason}",
                    "bodyHtml": body_html,
                },
                headers=headers,
            )
            resp.raise_for_status()
            LOG.info("floor alert sent to %s (status=%d)", KAISYA_ALERT_TO, resp.status_code)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("floor alert send failed: %s", exc)


# ── LangGraph state ───────────────────────────────────────────────────

class OrgState(TypedDict, total=False):
    # Raw metrics
    agent_runs_24h: int
    error_runs_24h: int
    pending_tasks: int
    critical_tasks: int
    at_risk_callers: int
    open_legal_cases: int
    urgent_legal_cases: int
    floor_violated: bool
    okr_attainment_avg: float      # average attainment_bps / 10000
    active_projects: int
    monthly_burn_jpy: float
    monthly_revenue_jpy: float
    infra_healthy: bool
    silent_agents: list[str]

    # Objective function components
    spirit_score: float
    wellbecoming_score: float
    feeling_score: float
    buffer_score: float
    u_total: float
    eta_value: float
    omega: float
    separation_delta: float        # Ω(t) - Ω(t-1)

    # Decisions + audit
    decisions: list[dict]          # [{type, title, agent, priority, context}]
    critical_alerts: int
    synthesis_text: str

    # Previous snapshot for delta
    prev_omega: float


# ── Collection ────────────────────────────────────────────────────────

def _collect_sync() -> dict[str, Any]:
    """Run all DB queries synchronously via sync_cursor."""
    result: dict[str, Any] = {}
    if True:
        client = get_kotoba_client()
        # Agent runs last 24h
        _res = client.q("""
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors,
              ARRAY_AGG(DISTINCT agent_id) FILTER (WHERE ran_at >= NOW() - INTERVAL '24 hours') AS active_agents
            FROM vertex_kaisya_agent_run
            WHERE ran_at >= NOW() - INTERVAL '24 hours'
        """)
        row = (_res[0] if _res else None)
        result["agent_runs_24h"] = int(row[0] or 0)
        result["error_runs_24h"] = int(row[1] or 0)
        active_agents = set(row[2] or [])

        # Silent agents (expected but no run in 48h)
        expected = {
            "kaisya_ceo_agent", "kaisya_coo_agent", "kaisya_clo_agent",
            "kaisya_eng_deploy_agent", "kaisya_eng_review_agent", "kaisya_eng_infra_agent",
            "kaisya_brand_agent", "kaisya_creative_agent",
        }
        result["silent_agents"] = sorted(expected - active_agents)

        # Pending tasks
        _res = client.q("""
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN priority = 1 THEN 1 ELSE 0 END) AS critical
            FROM vertex_kaisya_task
            WHERE status = 'pending'
        """)
        row = (_res[0] if _res else None)
        result["pending_tasks"] = int(row[0] or 0)
        result["critical_tasks"] = int(row[1] or 0)

        # Wellbecoming at-risk
        try:
            _res = client.q("SELECT COUNT(*) FROM mv_wellbecoming_at_risk")
            result["at_risk_callers"] = int((_res[0] if _res else None)[0] or 0)
        except Exception:  # noqa: BLE001
            result["at_risk_callers"] = 0

        # Wellbecoming floor violations
        try:
            _res = client.q("""
                SELECT COUNT(*) FROM vertex_kaisya_agent_run
                WHERE task_type = 'floorViolationAlert'
                  AND ran_at >= NOW() - INTERVAL '2 hours'
                  AND status = 'ok'
            """)
            result["floor_violated"] = int((_res[0] if _res else None)[0] or 0) > 0
        except Exception:  # noqa: BLE001
            result["floor_violated"] = False

        # Legal cases
        try:
            _res = client.q("""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN due_date IS NOT NULL
                           AND due_date::date <= CURRENT_DATE + INTERVAL '7 days'
                      THEN 1 ELSE 0 END) AS urgent
                FROM vertex_lawfirm_case
                WHERE status NOT IN ('closed', 'archived')
            """)
            row = (_res[0] if _res else None)
            result["open_legal_cases"] = int(row[0] or 0)
            result["urgent_legal_cases"] = int(row[1] or 0)
        except Exception:  # noqa: BLE001
            result["open_legal_cases"] = 0
            result["urgent_legal_cases"] = 0

        # OKR attainment
        try:
            _res = client.q("SELECT AVG(attainment_bps) FROM vertex_goal WHERE status != 'cancelled'")
            bps = (_res[0] if _res else None)[0] or 5000
            result["okr_attainment_avg"] = float(bps) / 10000.0
        except Exception:  # noqa: BLE001
            result["okr_attainment_avg"] = 0.5

        # Active projects
        try:
            _res = client.q("SELECT COUNT(*) FROM vertex_business_case WHERE status IN ('active','in_progress','pending')")
            result["active_projects"] = int((_res[0] if _res else None)[0] or 0)
        except Exception:  # noqa: BLE001
            result["active_projects"] = 0

        # Financial snapshot
        try:
            _res = client.q("""
                SELECT monthly_revenue_jpy, monthly_burn_jpy
                FROM vertex_strategy_snapshot
                ORDER BY snapshot_at DESC
                LIMIT 1
            """)
            row = (_res[0] if _res else None)
            if row:
                result["monthly_revenue_jpy"] = float(row[0] or 0)
                result["monthly_burn_jpy"] = float(row[1] or 0)
            else:
                result["monthly_revenue_jpy"] = 0.0
                result["monthly_burn_jpy"] = 1_000_000.0  # budget cap
        except Exception:  # noqa: BLE001
            result["monthly_revenue_jpy"] = 0.0
            result["monthly_burn_jpy"] = 1_000_000.0

        # Previous Ω(t-1)
        try:
            _res = client.q("""
                SELECT omega FROM vertex_kaisya_org_snapshot
                ORDER BY snapshot_at DESC
                LIMIT 1
            """)
            row = (_res[0] if _res else None)
            result["prev_omega"] = float(row[0]) if row else 0.5
        except Exception:  # noqa: BLE001
            result["prev_omega"] = 0.5

    # Infra health: lightweight check via RisingWave connectivity
    # (if we got here, RisingWave is reachable)
    result["infra_healthy"] = True
    return result


# ── Objective function computation ────────────────────────────────────

def _compute_objective(state: OrgState) -> tuple[float, float, float, float, float, float, float]:
    """
    Returns (spirit, wellbecoming, feeling, buffer, u_total, eta, omega).

    Spirit    = f(OKR attainment, η)
    Wellbec.  = f(active projects, delivery health)
    Feeling   = f(pending task pressure, legal case load)
    Buffer    = f(financial runway, infra health)
    η (eta)   = autonomous execution rate
    U_total   = min(axes) — floor dominance (Axiom 4: if any=0 → 0)
    Ω         = η × U_total
    """
    # η — autonomous execution efficiency
    total_possible = max(1, state.get("agent_runs_24h", 0) + state.get("pending_tasks", 0))
    tasks_pending  = state.get("pending_tasks", 0)
    critical       = state.get("critical_tasks", 0)
    error_runs     = state.get("error_runs_24h", 0)
    # η degrades with human gates outstanding and error runs
    gate_penalty  = min(1.0, (tasks_pending * 0.05 + critical * 0.1))
    error_penalty = min(0.3, error_runs * 0.05)
    eta = _clamp01(1.0 - gate_penalty - error_penalty)

    # Spirit: OKR health + η ≥ ETA_MIN
    okr = state.get("okr_attainment_avg", 0.5)
    eta_bonus = 1.0 if eta >= ETA_MIN_THRESHOLD else eta / ETA_MIN_THRESHOLD
    spirit = _clamp01((okr * 0.7 + eta_bonus * 0.3))

    # Wellbecoming: delivery + growth (proxy: active projects normalized)
    proj = min(1.0, state.get("active_projects", 0) / 5.0)  # 5 active projects = full
    silent_penalty = min(0.4, len(state.get("silent_agents", [])) * 0.1)
    wellbecoming = _clamp01(proj * 0.6 + 0.4 - silent_penalty)

    # Feeling: low pressure = high score
    legal_pressure = min(1.0, state.get("open_legal_cases", 0) * 0.1
                         + state.get("urgent_legal_cases", 0) * 0.2)
    task_pressure  = min(1.0, tasks_pending * 0.04)
    at_risk_pen    = min(0.3, state.get("at_risk_callers", 0) * 0.05)
    feeling = _clamp01(1.0 - legal_pressure * 0.5 - task_pressure * 0.3 - at_risk_pen * 0.2)

    # Buffer: financial runway + infra
    burn   = max(1.0, state.get("monthly_burn_jpy", 1_000_000.0))
    rev    = state.get("monthly_revenue_jpy", 0.0)
    # runway expressed as months; cap at 12 for normalization
    runway_months = min(12.0, rev / burn * 12.0) if rev > 0 else 0.5
    infra_score   = 1.0 if state.get("infra_healthy", True) else 0.2
    buffer = _clamp01((runway_months / 12.0) * 0.6 + infra_score * 0.4)

    # Floor constraint: floor_violated → feeling collapses
    if state.get("floor_violated", False):
        feeling = 0.0

    # U_total = min (bottleneck dominance, Axiom 3)
    u_total = min(spirit, wellbecoming, feeling, buffer)

    # Floor: spirit=0 kills U_total (Axiom 4)
    if spirit == 0.0:
        u_total = 0.0

    omega = _clamp01(eta * u_total)
    return spirit, wellbecoming, feeling, buffer, u_total, eta, omega


# ── Decision routing ──────────────────────────────────────────────────

def _route_decisions(state: OrgState, spirit: float, wellbecoming: float,
                     feeling: float, buffer: float, u_total: float,
                     eta: float, omega: float) -> list[dict]:
    """Produce a list of decisions the master loop will execute."""
    decisions: list[dict] = []

    # Critical: floor violated → wellbecoming team alert
    if state.get("floor_violated", False):
        decisions.append({
            "type": "wellbecoming_floor_alert",
            "title": "Well-Being floor violation — immediate intervention required",
            "agent": "kaisya_clo_agent",
            "priority": 1,
            "context": json.dumps({"at_risk": state.get("at_risk_callers", 0)}),
        })

    # At-risk callers → wellbecoming proactive connect
    if state.get("at_risk_callers", 0) > 0:
        decisions.append({
            "type": "wellbecoming_proactive",
            "title": f"{state['at_risk_callers']} at-risk callers — proactive connect",
            "agent": "kaisya_coo_agent",
            "priority": 2,
            "context": json.dumps({"at_risk_count": state.get("at_risk_callers")}),
        })

    # Legal urgent
    if state.get("urgent_legal_cases", 0) > 0:
        decisions.append({
            "type": "legal_urgent",
            "title": f"Legal deadline within 7d: {state['urgent_legal_cases']} case(s)",
            "agent": "kaisya_clo_agent",
            "priority": 1,
            "context": json.dumps({"urgent_count": state.get("urgent_legal_cases")}),
        })

    # OKR drift
    if spirit < 0.5:
        decisions.append({
            "type": "okr_drift",
            "title": f"OKR spirit score low ({spirit:.2f}) — CEO strategic review",
            "agent": "kaisya_ceo_agent",
            "priority": 1 if spirit < 0.3 else 2,
            "context": json.dumps({"spirit_score": spirit, "okr_attainment": state.get("okr_attainment_avg")}),
        })

    # Budget pressure
    if buffer < 0.4:
        decisions.append({
            "type": "budget_pressure",
            "title": f"Buffer score low ({buffer:.2f}) — financial review required",
            "agent": "kaisya_ceo_agent",
            "priority": 1 if buffer < 0.2 else 2,
            "context": json.dumps({"buffer_score": buffer, "burn_jpy": state.get("monthly_burn_jpy")}),
        })

    # Silent agents
    silent = state.get("silent_agents", [])
    if silent:
        decisions.append({
            "type": "agent_silent",
            "title": f"Agents silent (no runs in 48h): {', '.join(silent[:3])}",
            "agent": "kaisya_coo_agent",
            "priority": 2,
            "context": json.dumps({"silent_agents": silent}),
        })

    # Omega below threshold: general alert
    if omega < OMEGA_ALERT_THRESHOLD and not any(d["priority"] == 1 for d in decisions):
        decisions.append({
            "type": "omega_low",
            "title": f"Ω(t)={omega:.3f} below threshold — org health review",
            "agent": "kaisya_ceo_agent",
            "priority": 2,
            "context": json.dumps({
                "omega": omega, "eta": eta, "u_total": u_total,
                "spirit": spirit, "wellbecoming": wellbecoming,
                "feeling": feeling, "buffer": buffer,
            }),
        })

    # η low: too many human gates outstanding
    if eta < ETA_MIN_THRESHOLD:
        decisions.append({
            "type": "eta_low",
            "title": f"Autonomy η={eta:.2f} — {state.get('pending_tasks', 0)} tasks awaiting human approval",
            "agent": "kaisya_coo_agent",
            "priority": 2,
            "context": json.dumps({"eta": eta, "pending": state.get("pending_tasks"), "critical": state.get("critical_tasks")}),
        })

    return decisions


# ── LangGraph nodes ───────────────────────────────────────────────────

async def _node_load_org_state(state: OrgState) -> OrgState:
    """Collect all org metrics from RisingWave in background thread."""
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, _collect_sync)
    state.update(raw)  # type: ignore[typeddict-item]
    return state


async def _node_compute_objective(state: OrgState) -> OrgState:
    spirit, wellbecoming, feeling, buffer, u_total, eta, omega = _compute_objective(state)
    prev = state.get("prev_omega", omega)
    state["spirit_score"]      = spirit
    state["wellbecoming_score"] = wellbecoming
    state["feeling_score"]     = feeling
    state["buffer_score"]      = buffer
    state["u_total"]           = u_total
    state["eta_value"]         = eta
    state["omega"]             = omega
    state["separation_delta"]  = round(omega - prev, 4)
    LOG.info("Ω(t)=%.3f  η=%.2f  U=%.2f  [spirit=%.2f wb=%.2f feel=%.2f buf=%.2f]  Δ=%.3f",
             omega, eta, u_total, spirit, wellbecoming, feeling, buffer, omega - prev)
    return state


async def _node_decide_actions(state: OrgState) -> OrgState:
    decisions = _route_decisions(
        state,
        state.get("spirit_score", 0.5),
        state.get("wellbecoming_score", 0.5),
        state.get("feeling_score", 0.5),
        state.get("buffer_score", 0.5),
        state.get("u_total", 0.5),
        state.get("eta_value", 0.8),
        state.get("omega", 0.5),
    )

    # LLM synthesis (short prompt, low cost)
    if decisions:
        prompt = (
            f"Org state: Ω={state.get('omega',0):.3f}, η={state.get('eta_value',0):.2f}, "
            f"U={state.get('u_total',0):.2f}. "
            f"Pending human tasks: {state.get('pending_tasks',0)}. "
            f"Decisions identified: {[d['title'] for d in decisions[:3]]}. "
            f"In 1 sentence, give the CEO the top priority action for the next 30 minutes."
        )
        synthesis = await _llm_complete(prompt, max_tokens=120)
    else:
        synthesis = (
            f"All systems nominal. Ω={state.get('omega',0):.3f} "
            f"η={state.get('eta_value',0):.2f} U={state.get('u_total',0):.2f}. "
            "No human gates required — continuing autonomous operation."
        )

    state["decisions"]       = decisions
    state["critical_alerts"] = sum(1 for d in decisions if d.get("priority") == 1)
    state["synthesis_text"]  = synthesis
    return state


async def _node_execute_actions(state: OrgState) -> OrgState:
    """Create vertex_kaisya_task rows for each decision.
    High-priority decisions (priority=1) create tasks immediately.
    Low-priority (priority=2) only create tasks if Ω < threshold.
    """
    from kotodama.primitives import kaisya_ai_org  # avoid circular at module level

    decisions = state.get("decisions", [])
    omega = state.get("omega", 0.5)
    tasks_created = 0

    for dec in decisions:
        p = dec.get("priority", 2)
        if p == 1 or omega < OMEGA_ALERT_THRESHOLD:
            try:
                await kaisya_ai_org._create_task(
                    agent_id=dec.get("agent", "kaisya_ceo_agent"),
                    title=dec["title"],
                    context_json=dec.get("context"),
                    priority=p,
                    due_hours=4 if p == 1 else 24,
                )
                tasks_created += 1
            except Exception as exc:  # noqa: BLE001
                LOG.warning("createTask failed for '%s': %s", dec["title"][:40], exc)

    # Also write a master agent run log
    try:
        await kaisya_ai_org._write_run_log(
            agent_id="kaisya_master",
            process_id="kaisya_master_routine",
            task_type="masterRoutine",
            output_summary=state.get("synthesis_text", "")[:500],
            status="ok",
            tasks_created=tasks_created,
        )
    except Exception as exc:  # noqa: BLE001
        LOG.warning("writeRunLog failed: %s", exc)

    state["_tasks_created"] = tasks_created  # type: ignore[typeddict-item]
    return state


async def _node_write_snapshot(state: OrgState) -> OrgState:
    """Persist Ω(t) snapshot to vertex_kaisya_org_snapshot."""
    vertex_id = _vertex_id("orgSnapshot")
    now = _now_iso()
    decisions_json = json.dumps(state.get("decisions", []))[:4000]
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_kaisya_org_snapshot
              (vertex_id, snapshot_at, omega, eta_value, u_total,
               spirit_score, wellbecoming_score, feeling_score, buffer_score,
               separation_delta, decisions_json, actions_executed, tasks_created,
               agent_runs_24h, pending_tasks, at_risk_callers, open_legal_cases,
               floor_violated,
               owner_did, org_id, user_id, sensitivity_ord, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                vertex_id, now,
                state.get("omega", 0.0), state.get("eta_value", 0.0), state.get("u_total", 0.0),
                state.get("spirit_score", 0.0), state.get("wellbecoming_score", 0.0),
                state.get("feeling_score", 0.0), state.get("buffer_score", 0.0),
                state.get("separation_delta", 0.0),
                decisions_json,
                len(state.get("decisions", [])),
                state.get("_tasks_created", 0),  # type: ignore[typeddict-item]
                state.get("agent_runs_24h", 0),
                state.get("pending_tasks", 0),
                state.get("at_risk_callers", 0),
                state.get("open_legal_cases", 0),
                state.get("floor_violated", False),
                OWNER_DID, ORG_DID, ORG_DID, 1, now,
            ),
        )
    LOG.info("snapshot written: %s  Ω=%.3f", vertex_id, state.get("omega", 0.0))
    return state


# ── LangGraph construction ────────────────────────────────────────────

try:
    from langgraph.graph import END, StateGraph  # type: ignore
    _LG_OK = True
except ImportError:
    _LG_OK = False
    LOG.warning("langgraph not available — master routine will run in linear fallback mode")

def _build_master_graph():
    if not _LG_OK:
        return None
    g: StateGraph = StateGraph(OrgState)
    g.add_node("load_org_state",      _node_load_org_state)
    g.add_node("compute_objective",   _node_compute_objective)
    g.add_node("decide_actions",      _node_decide_actions)
    g.add_node("execute_actions",     _node_execute_actions)
    g.add_node("write_snapshot",      _node_write_snapshot)

    g.set_entry_point("load_org_state")
    g.add_edge("load_org_state",    "compute_objective")
    g.add_edge("compute_objective", "decide_actions")
    g.add_edge("decide_actions",    "execute_actions")
    g.add_edge("execute_actions",   "write_snapshot")
    g.add_edge("write_snapshot",    END)
    return g.compile()

_MASTER_GRAPH = None

def _get_master_graph():
    global _MASTER_GRAPH  # noqa: PLW0603
    if _MASTER_GRAPH is None:
        _MASTER_GRAPH = _build_master_graph()
    return _MASTER_GRAPH


async def _run_master_loop() -> dict[str, Any]:
    """Execute full master loop and return final state dict."""
    graph = _get_master_graph()
    initial: OrgState = {}  # type: ignore[typeddict-item]

    if graph is not None:
        result = await graph.ainvoke(initial)
        final: OrgState = result  # type: ignore[assignment]
    else:
        # Linear fallback (no LangGraph)
        s: OrgState = {}  # type: ignore[typeddict-item]
        s = await _node_load_org_state(s)
        s = await _node_compute_objective(s)
        s = await _node_decide_actions(s)
        s = await _node_execute_actions(s)
        s = await _node_write_snapshot(s)
        final = s

    return {
        "omega":              final.get("omega", 0.0),
        "eta_value":          final.get("eta_value", 0.0),
        "u_total":            final.get("u_total", 0.0),
        "spirit_score":       final.get("spirit_score", 0.0),
        "wellbecoming_score": final.get("wellbecoming_score", 0.0),
        "feeling_score":      final.get("feeling_score", 0.0),
        "buffer_score":       final.get("buffer_score", 0.0),
        "separation_delta":   final.get("separation_delta", 0.0),
        "decisions":          final.get("decisions", []),
        "critical_alerts":    final.get("critical_alerts", 0),
        "actions_executed":   len(final.get("decisions", [])),
        "tasks_created":      final.get("_tasks_created", 0),  # type: ignore[typeddict-item]
        "synthesis_text":     final.get("synthesis_text", ""),
    }


# ── Pyzeebe task handlers ─────────────────────────────────────────────

def register(worker: Any, timeout_ms: int = 180_000) -> None:
    """Register all master routine task handlers with the Zeebe worker."""

    @worker.task(task_type="kaisya.master.collectState", timeout_ms=timeout_ms)
    async def task_collect_state() -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _collect_sync)
        # Serialize for Zeebe variable transport
        return {"orgState": json.dumps(raw)}

    @worker.task(task_type="kaisya.master.evaluateObjective", timeout_ms=timeout_ms)
    async def task_evaluate_objective(orgState: str = "{}") -> dict[str, Any]:
        state: OrgState = json.loads(orgState)  # type: ignore[assignment]
        s = await _node_compute_objective(state)
        s = await _node_decide_actions(s)
        return {
            "omega":              s.get("omega", 0.0),
            "etaValue":           s.get("eta_value", 0.0),
            "uTotal":             s.get("u_total", 0.0),
            "spiritScore":        s.get("spirit_score", 0.0),
            "wellbecomingScore":  s.get("wellbecoming_score", 0.0),
            "feelingScore":       s.get("feeling_score", 0.0),
            "bufferScore":        s.get("buffer_score", 0.0),
            "separationDelta":    s.get("separation_delta", 0.0),
            "decisions":          json.dumps(s.get("decisions", [])),
            "criticalAlerts":     s.get("critical_alerts", 0),
            "synthesisText":      s.get("synthesis_text", ""),
        }

    @worker.task(task_type="kaisya.master.executeDecisions", timeout_ms=timeout_ms)
    async def task_execute_decisions(
        decisions: str = "[]",
        omega: float = 0.5,
    ) -> dict[str, Any]:
        from kotodama.primitives import kaisya_ai_org  # noqa: PLC0415

        dec_list: list[dict] = json.loads(decisions) if isinstance(decisions, str) else decisions
        tasks_created = 0
        for dec in dec_list:
            p = int(dec.get("priority", 2))
            if p == 1 or omega < OMEGA_ALERT_THRESHOLD:
                try:
                    await kaisya_ai_org._create_task(
                        agent_id=dec.get("agent", "kaisya_ceo_agent"),
                        title=dec["title"],
                        context_json=dec.get("context"),
                        priority=p,
                        due_hours=4 if p == 1 else 24,
                    )
                    tasks_created += 1
                except Exception as exc:  # noqa: BLE001
                    LOG.warning("createTask failed: %s", exc)
        try:
            await kaisya_ai_org._write_run_log(
                "kaisya_master", "kaisya_master_routine", "masterRoutine",
                f"Ω={omega:.3f} decisions={len(dec_list)} tasks={tasks_created}",
                tasks_created=tasks_created,
            )
        except Exception as exc:  # noqa: BLE001
            LOG.warning("runLog failed: %s", exc)
        return {"actionsExecuted": len(dec_list), "tasksCreated": tasks_created}

    @worker.task(task_type="kaisya.master.writeSnapshot", timeout_ms=60_000)
    async def task_write_snapshot(
        omega: float = 0.0,
        etaValue: float = 0.0,
        uTotal: float = 0.0,
        spiritScore: float = 0.0,
        wellbecomingScore: float = 0.0,
        feelingScore: float = 0.0,
        bufferScore: float = 0.0,
        separationDelta: float = 0.0,
        decisions: str = "[]",
        actionsExecuted: int = 0,
        tasksCreated: int = 0,
        criticalAlerts: int = 0,
        synthesisText: str = "",
    ) -> dict[str, Any]:
        vertex_id = _vertex_id("orgSnapshot")
        now = _now_iso()
        dec_list = json.loads(decisions) if isinstance(decisions, str) else decisions
        floor_violated = any(s == 0.0 for s in [spiritScore, wellbecomingScore, feelingScore, bufferScore])
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """
                INSERT INTO vertex_kaisya_org_snapshot
                  (vertex_id, snapshot_at, omega, eta_value, u_total,
                   spirit_score, wellbecoming_score, feeling_score, buffer_score,
                   separation_delta, decisions_json, actions_executed, tasks_created,
                   agent_runs_24h, pending_tasks, at_risk_callers, open_legal_cases,
                   floor_violated,
                   owner_did, org_id, user_id, sensitivity_ord, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    vertex_id, now, omega, etaValue, uTotal,
                    spiritScore, wellbecomingScore, feelingScore, bufferScore,
                    separationDelta,
                    json.dumps(dec_list)[:4000],
                    actionsExecuted, tasksCreated,
                    0, 0, 0, 0, floor_violated,
                    OWNER_DID, ORG_DID, ORG_DID, 1, now,
                ),
            )
        LOG.info(
            "master snapshot: Ω=%.3f η=%.2f U=%.2f tasks=%d floor=%s",
            omega, etaValue, uTotal, tasksCreated, floor_violated,
        )
        if omega < OMEGA_ALERT_THRESHOLD or floor_violated:
            await _send_floor_alert(omega, floor_violated, synthesisText)
        return {"snapshotVertexId": vertex_id, "omega": omega}

    # Register the full master loop as a single convenience handler too
    # (used when calling the BPMN dispatcher directly for testing)
    @worker.task(task_type="kaisya.master.runFull", timeout_ms=timeout_ms)
    async def task_run_full() -> dict[str, Any]:
        return await _run_master_loop()

    LOG.info(
        "kaisya.master registered: "
        "kaisya.master.{collectState,evaluateObjective,executeDecisions,writeSnapshot,runFull}"
    )


# Register LangGraph graph for graph_id dispatch
if _LG_OK:
    try:
        langgraph_registry.register("kaisya_master_routine", _build_master_graph)
        LOG.info("kaisya_master_routine registered in LangGraph registry")
    except Exception as _e:  # noqa: BLE001
        LOG.warning("LangGraph registry register failed: %s", _e)
