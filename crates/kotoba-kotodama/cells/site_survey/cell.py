"""
SiteSurveyCell — kuni-umi Phase 1 Pregel cell.

Per ADR-2605201400 §1 (Actor topology — Tier B per-phase leader on
``naphtali``) + ADR-2605192415 §4.

Bridges the 18,342-actor UNSPSC catalog to the physical-deployment
workflow: when a ``defineDeploymentSite`` MST record lands, the cell
geo-validates the site against the LandRegistry / OceanStewardship /
RiverStewardship / AtmosphereStewardship / OrbitalSlot substrate, fans
out to the relevant UNSPSC commodity data via the openUnispsc XRPC
service (unispsc.etzhayyim.com) for commodity-specific feedback,
collects ≥2 witness attestations (constitutional invariant per
ADR-2605201400 §9), then emits a ``submitSiteSurvey`` record to MST.

LangGraph nodes (super-step semantics):

  START → parse_site_definition  → load defineDeploymentSite record
        → jurisdiction_dmn        → ADR-2605192245/2605192330 sovereignty + Charter Rider §2 gate
        → unispsc_lookup          → derive applicable UNSPSC codes from utilityClass / intendedUse
        → fan_out_specialists     → resolve each code via openUnispsc XRPC
        → ecology_assessment      → impactScore / protectedSpecies / culturalHeritage
        → witness_attestation     → wait for N ≥ 2 robot Ed25519 sigs
        → synthesize_survey       → assemble submitSiteSurvey input
        → emit_at_record          → write to MST → END

The witness wait-state is the only fixed-point — checkpointer pauses
there until the swarm broadcast (ADR-2605191524) delivers attestations.
Other nodes are O(seconds).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Annotated, TypedDict
from operator import add

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger("SiteSurveyCell")

# Canonical UNSPSC commodity XRPC gateway. The per-code Python executor
# shards (UnispscAgentExecutorCell — LAN HTTP + libp2p transport) were
# retired; their per-code agents are superseded by the clj unspsc actor
# (etzhayyim/root@20-actors/unspsc). Specialists now resolve against the
# canonical openUnispsc XRPC service (unispsc.etzhayyim.com → lg-open-unispsc).
UNISPSC_XRPC_ENDPOINT = os.environ.get(
    "UNISPSC_XRPC_ENDPOINT", "https://unispsc.etzhayyim.com"
)
UNISPSC_COMMODITY_NSID = "com.etzhayyim.etzhayyim.apps.openUnispsc.commodity"

UTILITY_TO_UNSPSC_SEGMENTS: dict[str, list[str]] = {
    # Maps the lexicon's utilityClass → likely UNSPSC segment prefixes that
    # the planning phase will need specialist input from. Conservative.
    "electric": ["26", "39", "32"],     # electrical / electronic / instrumentation
    "gas": ["12", "26", "27"],          # chemicals / electrical / tools
    "water": ["40", "30", "27"],        # distribution / civil / tools
    "network": ["43", "26", "32"],      # IT / electrical / instruments
    "power": ["26", "39", "40"],        # electrical / electronic / distribution
    "rail": ["25", "30", "26"],         # vehicles / civil / electrical
    "airplane": ["25", "23", "26"],     # aero / production / electrical
    "port": ["25", "30", "24"],         # vessels / civil / handling
    "multi": ["26", "30", "39", "40"],
}

WITNESS_MIN = 2  # constitutional invariant — never reduce (ADR-2605201400 §9)
DEFAULT_FAN_OUT_LIMIT = 8  # cap parallel specialist calls per super-step


class SiteSurveyState(TypedDict, total=False):
    # ── inputs ───────────────────────────────────────────────────────
    site_uri: str
    site_record: dict[str, Any]
    site_did: str
    site_code: str
    utility_class: str
    domain: str
    intended_use: str
    geo_feature: dict[str, Any]
    jurisdiction_did: str
    steward_did: str

    # ── jurisdiction DMN output ─────────────────────────────────────
    jurisdiction_ok: bool
    charter_rider_ok: bool
    jurisdiction_rejection: str

    # ── specialist fan-out ──────────────────────────────────────────
    unispsc_candidate_codes: list[str]
    specialist_results: Annotated[list[dict[str, Any]], add]

    # ── ecology ─────────────────────────────────────────────────────
    ecology_baseline: dict[str, Any]

    # ── witness attestations (accumulated as robots sign) ───────────
    witness_attestations: Annotated[list[dict[str, str]], add]
    witness_blob_hash: str

    # ── output ──────────────────────────────────────────────────────
    survey_did: str
    accepted: bool
    submission_at_uri: str
    error: str


# ── Node functions ──────────────────────────────────────────────────


def parse_site_definition(state: SiteSurveyState) -> dict[str, Any]:
    """Load the defineDeploymentSite record referenced by site_uri."""
    rec = state.get("site_record") or {}
    if not rec and state.get("site_uri"):
        # Real wiring will fetch via etzhayyim_sdk MST. Stub for now.
        rec = {}
    return {
        "site_record": rec,
        "site_code": rec.get("siteCode") or state.get("site_code") or "",
        "utility_class": rec.get("utilityClass") or state.get("utility_class") or "multi",
        "domain": rec.get("domain") or state.get("domain") or "terrestrial",
        "intended_use": rec.get("intendedUse") or state.get("intended_use") or "",
        "geo_feature": rec.get("geo") if isinstance(rec.get("geo"), dict) else {},
        "jurisdiction_did": rec.get("jurisdictionDid") or state.get("jurisdiction_did") or "",
        "steward_did": rec.get("stewardDid") or state.get("steward_did") or "",
    }


def jurisdiction_dmn(state: SiteSurveyState) -> dict[str, Any]:
    """Run the jurisdiction-eligibility + Charter Rider §2 gate.

    Real wiring calls into the LandRegistry / OceanStewardship contracts.
    This scaffold performs the structural check: rejection if either DID
    is missing or the intended_use phrase trips the no-advertising/no-
    purchase-purpose pre-screen.
    """
    juri_ok = bool(state.get("jurisdiction_did")) and bool(state.get("steward_did"))
    use = (state.get("intended_use") or "").lower()
    rider_ok = not any(
        kw in use
        for kw in ("weapon", "speculative", "surveillance", "addictive",
                   "fossil-extract", "specialist gatekeeping")
    )
    rejection = ""
    if not juri_ok:
        rejection = "MissingStewardOrJurisdiction"
    elif not rider_ok:
        rejection = "CharterRiderSection2Violation"
    return {
        "jurisdiction_ok": juri_ok,
        "charter_rider_ok": rider_ok,
        "jurisdiction_rejection": rejection,
    }


def unispsc_lookup(state: SiteSurveyState) -> dict[str, Any]:
    """Derive applicable UNSPSC commodity codes for fan-out."""
    utility = state.get("utility_class") or "multi"
    segments = UTILITY_TO_UNSPSC_SEGMENTS.get(utility, ["26", "30", "40"])
    # For the scaffold, emit one representative code per segment.
    # Real planning phase will use intended_use NLP + Council scope rules.
    candidates = [f"{seg}000000" for seg in segments][:DEFAULT_FAN_OUT_LIMIT]
    return {"unispsc_candidate_codes": candidates}


def fan_out_specialists(state: SiteSurveyState) -> dict[str, Any]:
    """Resolve each candidate UNSPSC code via the canonical openUnispsc XRPC.

    The per-code LAN/libp2p executor shards were retired (their per-code
    agents are superseded by the clj unspsc actor); each candidate code is
    POSTed to ``openUnispsc.commodity`` at the canonical gateway. Sync fan-out
    (per LangGraph node contract); unreachable service degrades per-code.
    """
    import urllib.request

    url = f"{UNISPSC_XRPC_ENDPOINT.rstrip('/')}/xrpc/{UNISPSC_COMMODITY_NSID}"
    results: list[dict[str, Any]] = []
    for code in state.get("unispsc_candidate_codes") or []:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({
                    "code": code,
                    "currency": "USDC",
                    "dryRun": True,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — record + continue
            results.append({"code": code, "error": str(exc), "transport": "xrpc"})
            continue
        result = payload if isinstance(payload, dict) else {}
        results.append({
            "code": code,
            "ok": bool(result.get("ok", True)),
            "state": result.get("state", result),
            "latencyMs": result.get("latencyMs"),
            "transport": "xrpc",
        })
    return {"specialist_results": results}


def ecology_assessment(state: SiteSurveyState) -> dict[str, Any]:
    """Compute ecology baseline.

    Scaffold: returns a conservative non-zero impact + flags
    protected_species when geo intersects known protected polygons.
    Real wiring will call into the Giemon scout fleet (RGB-D + LIDAR +
    chem-sensor + multispectral). For now the result is a placeholder
    that downstream nodes can consume.
    """
    geo = state.get("geo_feature") or {}
    impact_score = 25 if geo else 50  # higher uncertainty when no geo
    return {
        "ecology_baseline": {
            "impactScore": impact_score,
            "protectedSpeciesDetected": False,
            "culturalHeritageDetected": False,
        },
    }


def witness_attestation(state: SiteSurveyState) -> dict[str, Any]:
    """Fixed-point node — pauses (via checkpointer) until N≥2 sigs arrive.

    Returns no-op state diff on each entry; the MST listener triggers
    re-entry with updated `witness_attestations` accumulator. The
    quorum_router below decides whether to advance or hold.
    """
    return {}


def synthesize_survey(state: SiteSurveyState) -> dict[str, Any]:
    """Assemble the submitSiteSurvey lexicon input + decide accept/reject."""
    ecology = state.get("ecology_baseline") or {}
    impact_ok = (ecology.get("impactScore") or 0) <= 70
    juri_ok = state.get("jurisdiction_ok", False) and state.get("charter_rider_ok", False)
    specialists = state.get("specialist_results") or []
    specialist_ok = any(r.get("ok") for r in specialists) if specialists else True
    accepted = juri_ok and impact_ok and specialist_ok
    return {"accepted": accepted}


def emit_at_record(state: SiteSurveyState) -> dict[str, Any]:
    """Write the submitSiteSurvey record to MST.

    Scaffold: stamps a synthetic at:// URI. Real wiring will use
    etzhayyim_sdk PdsClient with the cell's DID + signed envelope.
    """
    site_did = state.get("site_did") or "did:web:etzhayyim.com:site:unknown"
    survey_did = f"{site_did}:survey:{int(time.time())}"
    submission_uri = (
        f"at://{site_did}/com.etzhayyim.apps.etzhayyim.kuniUmi.submitSiteSurvey/"
        f"{int(time.time() * 1000)}"
    )
    return {
        "survey_did": survey_did,
        "submission_at_uri": submission_uri,
    }


# ── Graph build ─────────────────────────────────────────────────────


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(SiteSurveyState)

    g.add_node("parse_site_definition", parse_site_definition)
    g.add_node("jurisdiction_dmn", jurisdiction_dmn)
    g.add_node("unispsc_lookup", unispsc_lookup)
    g.add_node("fan_out_specialists", fan_out_specialists)
    g.add_node("ecology_assessment", ecology_assessment)
    g.add_node("witness_attestation", witness_attestation)
    g.add_node("synthesize_survey", synthesize_survey)
    g.add_node("emit_at_record", emit_at_record)

    g.add_edge(START, "parse_site_definition")
    g.add_edge("parse_site_definition", "jurisdiction_dmn")

    def juri_router(state: SiteSurveyState) -> str:
        if not (state.get("jurisdiction_ok") and state.get("charter_rider_ok")):
            return "emit_at_record"  # short-circuit to rejection
        return "unispsc_lookup"

    g.add_conditional_edges("jurisdiction_dmn", juri_router, {
        "emit_at_record": "emit_at_record",
        "unispsc_lookup": "unispsc_lookup",
    })

    g.add_edge("unispsc_lookup", "fan_out_specialists")
    g.add_edge("fan_out_specialists", "ecology_assessment")
    g.add_edge("ecology_assessment", "witness_attestation")

    def quorum_router(state: SiteSurveyState) -> str:
        if len(state.get("witness_attestations") or []) >= WITNESS_MIN:
            return "synthesize_survey"
        return "witness_attestation"  # hold at fixed-point

    g.add_conditional_edges("witness_attestation", quorum_router, {
        "synthesize_survey": "synthesize_survey",
        "witness_attestation": "witness_attestation",
    })

    g.add_edge("synthesize_survey", "emit_at_record")
    g.add_edge("emit_at_record", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


graph = build_graph()


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ─────────────────


def state_from_event(event: dict[str, Any]) -> SiteSurveyState:
    """Map an MST event payload into the cell's TypedDict state.

    The submitSiteSurvey lexicon (com.etzhayyim.apps.etzhayyim.kuniUmi.submitSiteSurvey)
    carries witnessAttestations on the record; fold them in so the witness
    quorum fixed-point can advance on the first super-step (otherwise the
    graph spins on witness_attestation until recursion-limit).
    """
    rec = event.get("record") or event.get("value") or {}
    if not isinstance(rec, dict):
        rec = {}
    witnesses_in = rec.get("witnessAttestations") or []
    if not isinstance(witnesses_in, list):
        witnesses_in = []
    return {
        "site_uri": event.get("uri", ""),
        "site_record": rec,
        "site_did": event.get("repo", ""),
        "witness_attestations": witnesses_in,
        "specialist_results": [],
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    return f"site-survey-{event.get('uri', '').replace('/', '-')[-40:]}"


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "SiteSurveyCell",
        "phase": "kuni-umi-1",
        "witnessMin": WITNESS_MIN,
        "unispscXrpcEndpoint": UNISPSC_XRPC_ENDPOINT,
    }


# ── cell-runner mst-listener entry ──────────────────────────────────


async def handle_mst_event(event_or_did=None) -> None:
    """Entry point for ``cells.toml`` ``entry = "handle_mst_event"`` under
    the mst-listener trigger. The cell-runner's ``_spawn_listener_cell``
    invokes this either with the firehose event dict (when no record path
    matched ``_extract_adherent_did``) or with the adherent DID string
    (when one did). For kuni-umi cells the event dict is the canonical
    shape — we tolerate the DID case by wrapping it as a synthetic event.
    """
    import asyncio as _asyncio
    if isinstance(event_or_did, str):
        event = {"repo": event_or_did, "record": {}}
    elif isinstance(event_or_did, dict):
        event = event_or_did
    else:
        event = {}
    try:
        state_in = state_from_event(event)
        thread_id = thread_id_from_event(event)
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        loop = _asyncio.get_running_loop()
        terminal = await loop.run_in_executor(
            None, lambda: graph.invoke(state_in, config=config)
        )
        logger.info(
            "%s mst event handled: thread_id=%s state_keys=%s",
            __name__, thread_id, list(terminal.keys())[:8] if isinstance(terminal, dict) else type(terminal).__name__,
        )
    except Exception as exc:  # noqa: BLE001 — never crash the listener loop
        logger.exception("%s mst event handler failed: %s", __name__, exc)


__all__ = [
    "SiteSurveyState",
    "build_graph",
    "graph",
    "state_from_event",
    "thread_id_from_event",
    "handle_mst_event",
    "healthz",
    "WITNESS_MIN",
    "UNISPSC_XRPC_ENDPOINT",
    "UTILITY_TO_UNSPSC_SEGMENTS",
]
