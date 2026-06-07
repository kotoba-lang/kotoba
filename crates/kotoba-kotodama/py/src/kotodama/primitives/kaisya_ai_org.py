"""etzhayyim Artificial Organism — kaisya AI agent primitives.

ADR-2604291800 §ai_org — 8 AI agents, timer-start cadence, human-gate via
vertex_kaisya_task.

Pyzeebe task types registered via register():
  kaisya.agent.writeRunLog    — write vertex_kaisya_agent_run row
  kaisya.agent.createTask     — insert vertex_kaisya_task row
  kaisya.ceo.synthesize       — LangGraph CEO strategic synthesis
  kaisya.coo.analyzeOps       — COO ops anomaly detection
  kaisya.clo.legalReason      — CLO legal reasoning (LingLing + deadline sweep)
  kaisya.eng.deployHealthCheck — deploy health probe (/_app/meta checks)
  kaisya.eng.infraProbe        — RisingWave + Zeebe + B2 health probe
  kaisya.brand.contentBriefing — brand content briefing generation
  kaisya.creative.assetPipeline — creative asset pipeline generation
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
import os
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("kaisya.ai_org")

OWNER_DID = "did:web:bpmn.etzhayyim.com"
ORG_DID   = "did:web:kaisya.etzhayyim.com"

# human_did for each agent (must match deps.toml [etzhayyim_agent.org_members])
_AGENT_HUMAN: dict[str, str] = {
    "kaisya_ceo_agent":        "did:web:j-kawasaki.etzhayyim.com",
    "kaisya_coo_agent":        "did:web:a-nakamura.etzhayyim.com",
    "kaisya_clo_agent":        "did:web:k-bakshi.etzhayyim.com",
    "kaisya_eng_deploy_agent": "did:web:t-chikada.etzhayyim.com",
    "kaisya_eng_review_agent": "did:web:f-tanaka.etzhayyim.com",
    "kaisya_eng_infra_agent":  "did:web:y-nishino.etzhayyim.com",
    "kaisya_brand_agent":      "did:web:t-ichihara.etzhayyim.com",
    "kaisya_creative_agent":   "did:web:k-takahashi.etzhayyim.com",
}

# ADR-2605010000: RunPod 6000 Ada is LLM SSoT. Murakumo removed from LLM path.


# ── Helpers ───────────────────────────────────────────────────────────

def _now_iso() -> str:
    # Kotoba Datom log TIMESTAMP (without timezone) rejects Z/+00:00 suffix.
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")

def _vertex_id(prefix: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://{OWNER_DID}/com.etzhayyim.apps.kaisya.{prefix}/{stamp}-{uuid.uuid4().hex[:8]}"

def _human_did(agent_id: str) -> str:
    return _AGENT_HUMAN.get(agent_id, ORG_DID)


def _llm_complete_sync(prompt: str, max_tokens: int = 512) -> str:
    """Single-turn LLM via llm.call_tier (ADR-2605010000 — RunPod 6000 Ada SSoT)."""
    try:
        from kotodama.llm import call_tier
        result = call_tier("structured", system="", user=prompt, max_tokens=max_tokens)
        return str(result.get("content", "")).strip() or "[empty]"
    except Exception as exc:
        LOG.warning("LLM call failed: %s", exc)
        return f"[LLM unavailable: {exc}]"


async def _llm_complete(prompt: str, max_tokens: int = 512) -> str:
    """Async wrapper — call_tier is sync, run in thread executor."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _llm_complete_sync, prompt, max_tokens)


# ── Core task handlers ────────────────────────────────────────────────

async def _write_run_log(
    agent_id: str,
    process_id: str,
    task_type: str,
    output_summary: str,
    status: str = "ok",
    tasks_created: int = 0,
) -> str:
    vertex_id = _vertex_id(f"agentRun.{agent_id}")
    ran_at = _now_iso()
    human_did = _human_did(agent_id)
    from datetime import datetime, timezone # R0: to_char(now(),..)
    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vertex_id,
        "agent_id": agent_id,
        "process_id": process_id,
        "task_type": task_type,
        "human_did": human_did,
        "status": status,
        "output_summary": output_summary[:2000] if output_summary else None,
        "tasks_created": tasks_created,
        "ran_at": ran_at,
        "owner_did": OWNER_DID,
        "org_id": ORG_DID,
        "user_id": human_did,
        "sensitivity_ord": 1,
        "created_at": ran_at,
    }
    client.insert_row("vertex_kaisya_agent_run", row_dict)
    LOG.info("writeRunLog: %s %s %s", agent_id, task_type, vertex_id)
    return vertex_id


async def _create_task(
    agent_id: str,
    title: str,
    context_json: str | None,
    priority: int = 2,
    due_hours: int = 24,
) -> str:
    vertex_id = _vertex_id(f"task.{agent_id}")
    human_did = _human_did(agent_id)
    now = _dt.datetime.now(tz=_dt.UTC)
    due_at = (now + _dt.timedelta(hours=due_hours)).strftime("%Y-%m-%d %H:%M:%S")
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vertex_id,
        "agent_id": agent_id,
        "human_did": human_did,
        "title": title,
        "context_json": context_json[:4000] if context_json else None,
        "priority": priority,
        "status": "pending",
        "due_at": due_at,
        "owner_did": OWNER_DID,
        "org_id": ORG_DID,
        "user_id": human_did,
        "sensitivity_ord": 1,
        "created_at": created_at,
    }
    client.insert_row("vertex_kaisya_task", row_dict)
    LOG.info("createTask: %s priority=%d '%s'", agent_id, priority, title[:60])
    return vertex_id


# ── CEO strategic synthesis ───────────────────────────────────────────

async def _ceo_synthesize(agent_metrics: list[dict], pending_counts: list[dict]) -> dict[str, Any]:
    metrics_txt = json.dumps(agent_metrics, ensure_ascii=False)[:800]
    pending_txt = json.dumps(pending_counts, ensure_ascii=False)[:400]
    prompt = (
        f"You are the CEO AI agent of etzhayyim Japan (etzhayyim). "
        f"Evaluate the following agent activity and pending task counts. "
        f"Identify if there is OKR drift (key objectives not progressing) and if any action is required.\n\n"
        f"Agent metrics (last 24h): {metrics_txt}\n"
        f"Pending tasks per human: {pending_txt}\n\n"
        f"Respond with JSON only: "
        f'{{ "briefing": "<1-2 sentence summary>", "okr_drift": true|false, '
        f'"action_required": true|false, "action_title": "<if action_required>", '
        f'"action_context": "<JSON string with details if action_required>" }}'
    )
    raw = await _llm_complete(prompt, max_tokens=400)
    try:
        # parse JSON from LLM response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end]) if start >= 0 else {}
    except Exception:  # noqa: BLE001
        data = {}

    return {
        "briefing_text": str(data.get("briefing", raw[:200])),
        "okr_drift": bool(data.get("okr_drift", False)),
        "action_required": bool(data.get("action_required", False)),
        "action_title": str(data.get("action_title", "CEO review required")),
        "action_context": str(data.get("action_context", raw[:500])),
    }


# ── COO ops analysis ──────────────────────────────────────────────────

async def _coo_analyze_ops(agent_status: list[dict]) -> dict[str, Any]:
    expected_agents = set(_AGENT_HUMAN.keys())
    seen_agents = {row.get("agent_id", "") for row in agent_status}
    silent = expected_agents - seen_agents
    error_agents = [r["agent_id"] for r in agent_status if int(r.get("error_count", 0)) > 0]

    anomaly = bool(silent or error_agents)
    report = (
        f"Agents active: {len(seen_agents)}/8. "
        f"Silent (no runs in 48h): {sorted(silent) or 'none'}. "
        f"Error runs: {error_agents or 'none'}."
    )
    title = "Ops anomaly: agent silence or errors detected"
    ctx = json.dumps({"silent": sorted(silent), "errors": error_agents})
    return {
        "report_text": report,
        "anomaly_detected": anomaly,
        "anomaly_title": title,
        "anomaly_context": ctx,
    }


# ── CLO legal reasoning ───────────────────────────────────────────────

async def _clo_legal_reason(open_cases: list[dict]) -> dict[str, Any]:
    today = _dt.date.today()
    urgent_cases = []
    for case in open_cases:
        due = case.get("due_date")
        if due:
            try:
                due_date = _dt.date.fromisoformat(str(due)[:10])
                if (due_date - today).days <= 7:
                    urgent_cases.append(case)
            except ValueError:
                pass

    urgent = bool(urgent_cases)
    report = (
        f"Open cases: {len(open_cases)}. "
        f"Due within 7 days: {len(urgent_cases)}. "
        + (f"Urgent: {[c.get('matter_ref','?') for c in urgent_cases]}" if urgent_cases else "All deadlines clear.")
    )
    title = f"Legal deadline urgent: {urgent_cases[0].get('matter_ref','?')}" if urgent_cases else "CLO review"
    ctx = json.dumps({"urgent_cases": [c.get("vertex_id") for c in urgent_cases]})
    return {
        "report_text": report,
        "urgent": urgent,
        "urgent_title": title,
        "urgent_context": ctx,
    }


# ── Eng: deploy health check ──────────────────────────────────────────

async def _eng_deploy_health_check() -> dict[str, Any]:
    endpoints = [
        "https://kaisya.etzhayyim.com/health",
        "https://bsky.etzhayyim.com/health",
        "https://atproto.etzhayyim.com/health",
        "https://murakumo.etzhayyim.com/health",
    ]
    failed = []
    try:
        import httpx  # type: ignore
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in endpoints:
                try:
                    resp = await client.get(url)
                    if not resp.is_success:
                        failed.append(f"{url} → {resp.status_code}")
                except Exception as exc:  # noqa: BLE001
                    failed.append(f"{url} → {exc}")
    except ImportError:
        failed.append("httpx not available")

    healthy = len(failed) == 0
    summary = (
        f"All {len(endpoints)} health endpoints OK."
        if healthy
        else f"{len(failed)} anomalies: {'; '.join(failed)}"
    )
    return {"healthy": healthy, "anomaly_workers": failed, "summary": summary}


# ── Eng: infra probe ──────────────────────────────────────────────────

async def _eng_infra_probe() -> dict[str, Any]:
    checks: list[str] = []
    failed: list[str] = []

    # Kotoba Datom log: simple COUNT query
    try:
        client = get_kotoba_client()
        # R0: count is always >= 0, so no need to check for None
        count = client.aggregate_where("vertex_kaisya_agent_run", "count", "*", None, None)
        checks.append("Kotoba Datom log OK")
    except Exception as exc:  # noqa: BLE001
        failed.append(f"Kotoba Datom log: {exc}")

    # Zeebe dispatcher HTTP probe
    try:
        import httpx  # type: ignore
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://dispatcher.etzhayyim.com/health")
            if resp.is_success:
                checks.append("Zeebe dispatcher OK")
            else:
                failed.append(f"Zeebe dispatcher {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        failed.append(f"Zeebe dispatcher: {exc}")

    healthy = len(failed) == 0
    summary = "; ".join(checks + failed)
    return {"healthy": healthy, "failed_services": failed, "summary": summary}


# ── Brand: content briefing ───────────────────────────────────────────

async def _brand_content_briefing(activity_summary: list[dict]) -> dict[str, Any]:
    top = activity_summary[:5]
    top_txt = ", ".join(f"{r.get('collection','?')}×{r.get('count','?')}" for r in top)
    briefing = f"Platform activity (24h): {top_txt}. Content calendar: continue platform updates."
    return {
        "briefing_text": briefing,
        "needs_approval": False,
        "approval_title": "",
        "approval_context": "",
    }


# ── Creative: asset pipeline ──────────────────────────────────────────

async def _creative_asset_pipeline(brand_requests: list[dict]) -> dict[str, Any]:
    pipeline = f"{len(brand_requests)} brand request(s) queued for creative pipeline."
    needs = len(brand_requests) > 3
    return {
        "pipeline_text": pipeline,
        "needs_signoff": needs,
        "signoff_title": f"Creative direction approval for {len(brand_requests)} requests",
        "signoff_context": json.dumps([r.get("title", "") for r in brand_requests[:5]]),
    }


# ── Pyzeebe registration ──────────────────────────────────────────────

def register(worker: Any, timeout_ms: int = 120_000) -> None:
    """Register all kaisya AI Org task handlers with the Zeebe worker."""

    @worker.task(task_type="kaisya.agent.writeRunLog", timeout_ms=timeout_ms)
    async def task_write_run_log(
        agent_id: str = "",
        process_id: str = "",
        task_type: str = "",
        output_summary: str = "",
        status: str = "ok",
        tasks_created_preview: int = 0,
    ) -> dict[str, Any]:
        vid = await _write_run_log(agent_id, process_id, task_type, output_summary, status)
        return {"run_vertex_id": vid}

    @worker.task(task_type="kaisya.agent.createTask", timeout_ms=timeout_ms)
    async def task_create_task(
        agent_id: str = "",
        title: str = "",
        context_json: str | None = None,
        priority: int = 2,
    ) -> dict[str, Any]:
        vid = await _create_task(agent_id, title, context_json, priority)
        return {"task_vertex_id": vid, "tasks_created": 1}

    @worker.task(task_type="kaisya.ceo.synthesize", timeout_ms=timeout_ms)
    async def task_ceo_synthesize(
        agent_metrics: list | None = None,
        pending_counts: list | None = None,
    ) -> dict[str, Any]:
        result = await _ceo_synthesize(agent_metrics or [], pending_counts or [])
        return result

    @worker.task(task_type="kaisya.coo.analyzeOps", timeout_ms=timeout_ms)
    async def task_coo_analyze_ops(
        agent_status: list | None = None,
    ) -> dict[str, Any]:
        result = await _coo_analyze_ops(agent_status or [])
        return result

    @worker.task(task_type="kaisya.clo.legalReason", timeout_ms=timeout_ms)
    async def task_clo_legal_reason(
        open_cases: list | None = None,
    ) -> dict[str, Any]:
        result = await _clo_legal_reason(open_cases or [])
        return result

    @worker.task(task_type="kaisya.eng.deployHealthCheck", timeout_ms=timeout_ms)
    async def task_eng_deploy_health_check() -> dict[str, Any]:
        return await _eng_deploy_health_check()

    @worker.task(task_type="kaisya.eng.infraProbe", timeout_ms=timeout_ms)
    async def task_eng_infra_probe() -> dict[str, Any]:
        return await _eng_infra_probe()

    @worker.task(task_type="kaisya.brand.contentBriefing", timeout_ms=timeout_ms)
    async def task_brand_content_briefing(
        activity_summary: list | None = None,
    ) -> dict[str, Any]:
        return await _brand_content_briefing(activity_summary or [])

    @worker.task(task_type="kaisya.creative.assetPipeline", timeout_ms=timeout_ms)
    async def task_creative_asset_pipeline(
        brand_requests: list | None = None,
    ) -> dict[str, Any]:
        return await _creative_asset_pipeline(brand_requests or [])

    LOG.info(
        "kaisya.ai_org registered: "
        "kaisya.agent.{writeRunLog,createTask}, "
        "kaisya.ceo.synthesize, kaisya.coo.analyzeOps, kaisya.clo.legalReason, "
        "kaisya.eng.{deployHealthCheck,infraProbe}, "
        "kaisya.brand.contentBriefing, kaisya.creative.assetPipeline"
    )
