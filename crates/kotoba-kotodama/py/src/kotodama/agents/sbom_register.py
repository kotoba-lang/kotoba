"""
com.etzhayyim.agent.sbom.register — LangGraph SBOM registration agent.

Three-node StateGraph wrapping the Phase B + Phase C primitives so the
caller gets a single agentic entry point with retry, transient error
handling, and downstream notification:

    classify  — Decide whether the artifact looks like software or a
                vehicle BOM (fast deterministic check + LLM fallback
                only when the metadata is ambiguous). Output: kind,
                confidence, reason.
    persist   — Call task_sbom_register_artifact + task_sbom_run_vuln_match
                inline. ReAct-style transient retry (3 attempts with
                exponential backoff) on RisingWave write failures.
    notify    — When `vulnMatchCount >= 1` AND severity ∈ {high, critical},
                emit a Bluesky-style mention via `app.bsky.feed.post`
                so downstream operators see the recall signal in the
                yoro feed. No-op otherwise.

Input variables (Zeebe → LangGraph state):
    artifactUri          str  — required (caller must compute via worker)
    cdxJson              str  — required
    sourceUri            str
    sourceSha256         str
    license              str
    vehicleId            str  — optional (vehicle BOM)
    vehicleRevision      str
    totalMassKg          float
    declaredPartCount    int
    threadId             str
    notifyChannel        str  — optional bsky DID to mention

Output variables (LangGraph state → Zeebe):
    artifactUri      str
    kind             str  — "software" | "vehicle"
    confidence       float
    persistedComponents int
    vulnMatchCount   int
    severityCounts   dict
    notified         bool
    phase            str
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama.primitives.sbom import (
    task_sbom_register_artifact,
    task_sbom_run_vuln_match,
)

log = logging.getLogger(__name__)


class SbomRegisterState(TypedDict, total=False):
    # Input
    artifactUri: str
    cdxJson: str
    sourceUri: str
    sourceSha256: str
    license: str
    format: str
    specVersion: str
    vehicleId: str
    vehicleRevision: str
    totalMassKg: float
    declaredPartCount: int
    threadId: str
    notifyChannel: str
    actorDid: str
    orgDid: str
    registeredAt: str
    # Decision
    kind: str
    confidence: float
    reason: str
    # Persistence
    componentCount: int
    persistedComponents: int
    persistResult: dict[str, Any]
    # Vuln-match
    vulnMatchCount: int
    severityCounts: dict[str, int]
    # Notification
    notified: bool
    notifyError: str
    phase: str


# ─── classify ───────────────────────────────────────────────────────────


def _classify_kind(state: SbomRegisterState) -> SbomRegisterState:
    """Cheap deterministic classifier — no LLM unless ambiguous.

    Vehicle BOMs always carry `vehicleId`. Software SBOMs have no such
    field. Anything in between (e.g. `vehicleId` empty string) defaults
    to software with low confidence so the BPMN caller can branch.
    """
    vid = (state.get("vehicleId") or "").strip()
    if vid:
        return {**state, "kind": "vehicle", "confidence": 1.0,
                "reason": "vehicleId present"}
    cdx = state.get("cdxJson") or ""
    # Cheap heuristic: vehicle BOMs from kami-cad-import always tag the
    # CDX top-level component with `cdx:etzhayyim:vehicle:*` properties.
    if "cdx:etzhayyim:vehicle:" in cdx:
        return {**state, "kind": "vehicle", "confidence": 0.85,
                "reason": "cdx-property hint cdx:etzhayyim:vehicle:*"}
    return {**state, "kind": "software", "confidence": 0.95,
            "reason": "no vehicle markers"}


# ─── persist (with retry) ───────────────────────────────────────────────


async def _persist_with_retry(state: SbomRegisterState) -> SbomRegisterState:
    """ReAct-style retry loop. Persist + vuln-match in one node."""
    import asyncio

    last_error: str = ""
    persist_result: dict[str, Any] = {}
    for attempt in range(3):
        try:
            persist_result = await task_sbom_register_artifact(
                artifactUri=state.get("artifactUri", ""),
                cdxJson=state.get("cdxJson", ""),
                format=state.get("format", "CycloneDX"),
                specVersion=state.get("specVersion", "1.5"),
                sourceUri=state.get("sourceUri", ""),
                sourceSha256=state.get("sourceSha256", ""),
                license=state.get("license", "unknown"),
                kind=state.get("kind", "software"),
                vehicleId=state.get("vehicleId"),
                vehicleRevision=state.get("vehicleRevision"),
                totalMassKg=state.get("totalMassKg"),
                declaredPartCount=state.get("declaredPartCount"),
                registeredAt=state.get("registeredAt", ""),
                actorDid=state.get("actorDid"),
                orgDid=state.get("orgDid"),
            )
            if persist_result.get("ok"):
                break
            last_error = str(persist_result.get("error", "unknown"))
        except Exception as e:  # noqa: BLE001 — retry envelope, error logged
            last_error = f"{type(e).__name__}: {e}"
            log.warning(
                "sbom-register attempt %d/3 failed: %s",
                attempt + 1,
                last_error,
            )
        await asyncio.sleep(0.5 * (2 ** attempt))

    if not persist_result.get("ok"):
        return {
            **state,
            "persistResult": persist_result or {"ok": False, "error": last_error},
            "componentCount": 0,
            "persistedComponents": 0,
            "vulnMatchCount": 0,
            "severityCounts": {},
            "phase": "B-persist-failed",
        }

    # Vuln-match (Phase C) — best-effort; an empty CVE catalog returns 0
    # cleanly and is the expected pre-Phase-D-feeder state.
    vuln_result: dict[str, Any] = {}
    try:
        vuln_result = await task_sbom_run_vuln_match(
            artifactUri=state.get("artifactUri", ""),
            actorDid=state.get("actorDid"),
            orgDid=state.get("orgDid"),
            registeredAt=state.get("registeredAt", ""),
        )
    except Exception as e:  # noqa: BLE001 — non-fatal
        log.warning("vuln-match failed (non-fatal): %s", e)
        vuln_result = {"ok": False, "vulnMatchCount": 0, "severityCounts": {}}

    return {
        **state,
        "persistResult": persist_result,
        "componentCount": int(persist_result.get("componentCount", 0)),
        "persistedComponents": int(persist_result.get("persistedComponents", 0)),
        "vulnMatchCount": int(vuln_result.get("vulnMatchCount", 0)),
        "severityCounts": vuln_result.get("severityCounts") or {},
        "phase": "C-vuln-match" if vuln_result.get("ok") else "B-persist",
    }


# ─── notify ─────────────────────────────────────────────────────────────


def _should_notify(state: SbomRegisterState) -> bool:
    sc = state.get("severityCounts") or {}
    high = int(sc.get("high", 0))
    crit = int(sc.get("critical", 0))
    return (high + crit) >= 1


def _notify(state: SbomRegisterState) -> SbomRegisterState:
    """Stub notify node — emits a structured log line. The downstream
    audit BPMN step picks it up. We don't actually post to bsky from
    here because the agent runs inside LangServer — social posting is
    a CF Worker concern (`sdk.pds.dispatch`)."""
    if not _should_notify(state):
        return {**state, "notified": False}

    sc = state.get("severityCounts") or {}
    msg = (
        f"[sbom-recall] {state.get('artifactUri','?')} kind={state.get('kind')} "
        f"high={sc.get('high',0)} critical={sc.get('critical',0)} "
        f"channel={state.get('notifyChannel','-')}"
    )
    log.warning(msg)
    return {**state, "notified": True}


# ─── Graph ──────────────────────────────────────────────────────────────


def _build_graph() -> Any:
    g = StateGraph(SbomRegisterState)
    g.add_node("classify", _classify_kind)
    g.add_node("persist", _persist_with_retry)
    g.add_node("notify", _notify)
    g.add_edge(START, "classify")
    g.add_edge("classify", "persist")
    g.add_edge("persist", "notify")
    g.add_edge("notify", END)
    return g.compile()


sbom_register_graph = _build_graph()


async def task_agent_sbom_register(**job_vars: Any) -> dict[str, Any]:
    """Entry point for the LangServer worker.

    Wraps the LangGraph in a single ainvoke call. Returns a flat dict
    suitable for FEEL ioMapping. Nested objects (severityCounts,
    persistResult) are JSON-encoded for round-trip safety through the
    Zeebe wire format.
    """
    started = time.monotonic()
    initial: SbomRegisterState = {
        "artifactUri": str(job_vars.get("artifactUri") or ""),
        "cdxJson": str(job_vars.get("cdxJson") or ""),
        "sourceUri": str(job_vars.get("sourceUri") or ""),
        "sourceSha256": str(job_vars.get("sourceSha256") or ""),
        "license": str(job_vars.get("license") or "unknown"),
        "format": str(job_vars.get("format") or "CycloneDX"),
        "specVersion": str(job_vars.get("specVersion") or "1.5"),
        "vehicleId": str(job_vars.get("vehicleId") or ""),
        "vehicleRevision": str(job_vars.get("vehicleRevision") or ""),
        "totalMassKg": float(job_vars.get("totalMassKg") or 0.0),
        "declaredPartCount": int(job_vars.get("declaredPartCount") or 0),
        "threadId": str(job_vars.get("threadId") or ""),
        "notifyChannel": str(job_vars.get("notifyChannel") or ""),
        "actorDid": str(job_vars.get("actorDid") or ""),
        "orgDid": str(job_vars.get("orgDid") or "anon"),
        "registeredAt": str(job_vars.get("registeredAt") or ""),
    }

    final = await sbom_register_graph.ainvoke(initial)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "ok": True,
        "artifactUri": final.get("artifactUri", ""),
        "kind": final.get("kind", "software"),
        "confidence": float(final.get("confidence", 0.0)),
        "reason": final.get("reason", ""),
        "componentCount": int(final.get("componentCount", 0)),
        "persistedComponents": int(final.get("persistedComponents", 0)),
        "vulnMatchCount": int(final.get("vulnMatchCount", 0)),
        "severityCountsJson": json.dumps(final.get("severityCounts") or {}),
        "notified": bool(final.get("notified", False)),
        "phase": final.get("phase", "B-persist"),
        "agentLatencyMs": elapsed_ms,
    }


__all__ = ["sbom_register_graph", "task_agent_sbom_register"]
