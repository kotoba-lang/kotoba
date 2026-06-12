"""
DecommissionCell — kuni-umi Phase 6 Pregel cell.

Per ADR-2605201400 §1 (Actor topology — Tier B end-of-life leader on
``dan``). The cell terminates the lifecycle of a deployment site: it
detects lifespan expiry (cron), accepts governance-vote / force-majeure
/ community-recall triggers, schedules an urban-mining handoff to the
Giemon fleet (per ``60-apps/etzhayyim-project-open-robo/docs/urban-mining-automation-v1.md``),
orchestrates dismantling, then verifies that the land was returned to
its natural state under the constitutional inalienability rule per
ADR-2605192245 (donated land is waqf-equivalent — it cannot be
transferred or burned, only returned to the Tree of Life trust in its
natural condition).

Decommission has no dedicated lexicon — it composes the existing
land-stewardship + land-return record types and emits a permanent
decommission record referenced by both.

LangGraph nodes (super-step semantics):

  START → lifespan_expiry_check    → cron-driven check vs commissionedAt + lifespanYears
        → trigger_router           → conditional fan-out:
              ├─ schedule_urban_mining  (lifespan-expiry / governance-vote /
              │                         force-majeure / community-recall)
              └─ END                    (no trigger fired — no-op super-step)
        → schedule_urban_mining    → emit urbanMiningPlanCid + Giemon handoff (placeholder)
        → dismantle_orchestration  → Giemon fleet dismantles (placeholder)
        → verify_land_return       → fixed-point until N >= 2 witness sigs confirm land returned
        → emit_decommission_record → write permanent decommission record → END

The land-return witness wait-state is the only fixed-point — checkpointer
pauses there until robot witnesses attest that the land has been
returned to its natural state per ADR-2605192245 inalienability.
"""

from __future__ import annotations

import logging
import time
from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("DecommissionCell")

# ── Constants (constitutional invariants) ──────────────────────────


# ADR-2605201400 §9 / ADR-2605192245: land-return attestation requires
# N >= 2 independent robot Ed25519 signatures (same invariant as the
# audit-witness path). NEVER reduce.
WITNESS_MIN = 2


# Valid decommission trigger reasons. lifespan-expiry is the cron path;
# governance-vote requires a Council deliberation (ADR-2605201400);
# force-majeure is an emergency path (e.g. natural disaster); community-
# recall is the 1 SBT = 1 vote path per ADR-2605192315.
VALID_TRIGGER_REASONS = (
    "lifespan-expiry",
    "governance-vote",
    "force-majeure",
    "community-recall",
)


# Urban-mining handoff target per fleet.toml. The Giemon fleet (open-
# robo) consumes the urbanMiningPlanCid + executes physical material
# recovery. The doc path is informational — runtime handoff goes via
# the swarm broadcast channel.
URBAN_MINING_DOC = (
    "60-apps/etzhayyim-project-open-robo/docs/urban-mining-automation-v1.md"
)


class DecommissionState(TypedDict, total=False):
    # ── inputs (composed from land-stewardship records) ────────────
    site_did: str
    plan_did: str
    lifespan_years: int
    commissioned_at: str  # ISO-8601 datetime
    lifespan_expiry_at: str  # computed: commissionedAt + lifespanYears

    # ── trigger inputs ─────────────────────────────────────────────
    governance_vote_passed: bool
    decommission_trigger_reason: str  # one of VALID_TRIGGER_REASONS
    triggered: bool  # set by lifespan_expiry_check / trigger_router

    # ── urban mining handoff ───────────────────────────────────────
    urban_mining_plan_cid: str

    # ── land return ────────────────────────────────────────────────
    witness_attestations: Annotated[list[dict[str, str]], add]
    land_return_attested: bool
    land_returned_at: str

    # ── output (permanent decommission record) ─────────────────────
    decommission_did: str
    decommission_record_at_uri: str
    error: str


# ── Helpers ─────────────────────────────────────────────────────────


def _parse_iso_to_epoch(iso: str) -> float:
    """Parse an ISO-8601 datetime to epoch seconds, tolerant of missing TZ."""
    if not iso:
        return 0.0
    fmts = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")
    for fmt in fmts:
        try:
            return time.mktime(time.strptime(iso[: len(fmt) + 4], fmt))
        except (ValueError, TypeError):
            continue
    return 0.0


# ── Node functions ──────────────────────────────────────────────────


def lifespan_expiry_check(state: DecommissionState) -> dict[str, Any]:
    """Cron-triggered check: has commissionedAt + lifespanYears passed?

    Sets ``triggered=True`` and ``decommission_trigger_reason="lifespan-expiry"``
    when expiry has elapsed. If a governance-vote / force-majeure /
    community-recall reason was already provided in state, preserves
    that and marks triggered as well.
    """
    existing_reason = state.get("decommission_trigger_reason") or ""
    if existing_reason in VALID_TRIGGER_REASONS:
        # External trigger already supplied; honor it.
        return {
            "triggered": True,
            "decommission_trigger_reason": existing_reason,
            "lifespan_expiry_at": state.get("lifespan_expiry_at") or "",
        }

    commissioned = state.get("commissioned_at") or ""
    lifespan_years = int(state.get("lifespan_years") or 0)
    expiry_epoch = 0.0
    expiry_iso = ""
    if commissioned and lifespan_years > 0:
        base = _parse_iso_to_epoch(commissioned)
        if base > 0:
            expiry_epoch = base + (lifespan_years * 365.25 * 24 * 3600)
            expiry_iso = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(expiry_epoch)
            )

    expired = expiry_epoch > 0 and expiry_epoch < time.time()
    return {
        "triggered": expired,
        "decommission_trigger_reason": "lifespan-expiry" if expired else "",
        "lifespan_expiry_at": expiry_iso,
    }


def schedule_urban_mining(state: DecommissionState) -> dict[str, Any]:
    """Emit the urbanMiningPlanCid and hand off to the Giemon fleet.

    Scaffold: stamps a synthetic CID. Real wiring will compose the
    plan from the site's deployment record (bill of materials,
    recoverable substrates, hazard inventory) and publish via the
    swarm broadcast channel to the open-robo Giemon fleet per
    ``URBAN_MINING_DOC``.
    """
    cid = state.get("urban_mining_plan_cid") or (
        f"bafkreig-urban-mining-{int(time.time())}"
    )
    return {"urban_mining_plan_cid": cid}


def dismantle_orchestration(state: DecommissionState) -> dict[str, Any]:
    """Giemon fleet dismantles the site.

    Scaffold: no-op. Real wiring polls the Giemon fleet's
    `dismantle.progress` channel and accumulates witness sigs as each
    physical module is recovered.
    """
    return {}


def verify_land_return(state: DecommissionState) -> dict[str, Any]:
    """Fixed-point — pauses until N >= 2 sigs confirm land returned.

    ADR-2605192245 inalienability rule: donated land cannot be
    transferred, burned, or sold. It can only be returned to the Tree
    of Life trust in its natural condition. Witnesses must attest that
    the site has been restored.
    """
    return {}


def emit_decommission_record(state: DecommissionState) -> dict[str, Any]:
    """Write the permanent decommission record to MST.

    Scaffold: stamps a synthetic at:// URI + decommissionDid + landReturnedAt.
    Real wiring will write a composed record referencing both the
    land-stewardship record (closed) and the land-return record (new)
    per ADR-2605192245.
    """
    site_did = state.get("site_did") or "did:web:etzhayyim.com:site:unknown"
    now_ns = int(time.time() * 1000)
    decom_did = f"{site_did}:decommission:{int(time.time())}"
    record_uri = (
        f"at://{site_did}/com.etzhayyim.apps.etzhayyim.kuniUmi.recordDecommission/"
        f"{now_ns}"
    )
    landed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "decommission_did": decom_did,
        "decommission_record_at_uri": record_uri,
        "land_return_attested": True,
        "land_returned_at": landed_at,
    }


# ── Graph build ─────────────────────────────────────────────────────


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(DecommissionState)

    g.add_node("lifespan_expiry_check", lifespan_expiry_check)
    g.add_node("schedule_urban_mining", schedule_urban_mining)
    g.add_node("dismantle_orchestration", dismantle_orchestration)
    g.add_node("verify_land_return", verify_land_return)
    g.add_node("emit_decommission_record", emit_decommission_record)

    g.add_edge(START, "lifespan_expiry_check")

    def trigger_router(state: DecommissionState) -> str:
        """Conditional edge — proceed only when a valid trigger fired.

        Routing:
          - any valid trigger (lifespan-expiry / governance-vote /
            force-majeure / community-recall) → schedule_urban_mining
          - no trigger → END (cron tick was a no-op for this site)
        """
        reason = state.get("decommission_trigger_reason") or ""
        if state.get("triggered") and reason in VALID_TRIGGER_REASONS:
            return "schedule_urban_mining"
        return "end"

    g.add_conditional_edges("lifespan_expiry_check", trigger_router, {
        "schedule_urban_mining": "schedule_urban_mining",
        "end": END,
    })

    g.add_edge("schedule_urban_mining", "dismantle_orchestration")
    g.add_edge("dismantle_orchestration", "verify_land_return")

    def witness_router(state: DecommissionState) -> str:
        if len(state.get("witness_attestations") or []) >= WITNESS_MIN:
            return "emit_decommission_record"
        return "verify_land_return"  # hold at fixed-point

    g.add_conditional_edges("verify_land_return", witness_router, {
        "emit_decommission_record": "emit_decommission_record",
        "verify_land_return": "verify_land_return",
    })

    g.add_edge("emit_decommission_record", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


graph = build_graph()


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ─────────────────


def state_from_event(event: dict[str, Any]) -> DecommissionState:
    """Map an MST event payload into the cell's TypedDict state.

    Decommission has no dedicated lexicon — it composes inputs from
    land-stewardship + land-return records (and may be invoked by the
    monthly cron with an empty record).
    """
    rec = event.get("record") or event.get("value") or {}
    if not isinstance(rec, dict):
        rec = {}
    return {
        "site_did": rec.get("siteDid") or event.get("repo", ""),
        "plan_did": rec.get("planDid") or "",
        "lifespan_years": int(rec.get("lifespanYears") or 0),
        "commissioned_at": rec.get("commissionedAt") or "",
        "governance_vote_passed": bool(rec.get("governanceVotePassed") or False),
        "decommission_trigger_reason": rec.get("decommissionTriggerReason") or "",
        "witness_attestations": list(rec.get("witnessAttestations") or []),
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    return f"decommission-{event.get('uri', '').replace('/', '-')[-40:]}"


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "DecommissionCell",
        "phase": "kuni-umi-6",
        "trigger": "cron + governance-vote + lifespan-expiry-monitor",
        "cron": "0 0 1 * *",
        "witnessMin": WITNESS_MIN,
        "validTriggerReasons": list(VALID_TRIGGER_REASONS),
        "urbanMiningHandoff": URBAN_MINING_DOC,
    }


# ── cell-runner cron entry ─────────────────────────────────────────


async def cron_fire() -> None:
    """Cron entry — fired by cell-runner on the schedule from cells.toml."""
    import asyncio as _asyncio
    try:
        state_in = {}  # cron firing has no event payload
        thread_id = f"decommission-cron-{int(__import__('time').time())}"
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        loop = _asyncio.get_running_loop()
        terminal = await loop.run_in_executor(
            None, lambda: graph.invoke(state_in, config=config)
        )
        logger.info(
            "decommission cron fired: thread_id=%s state_keys=%s",
            thread_id, list(terminal.keys())[:8] if isinstance(terminal, dict) else type(terminal).__name__,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("decommission cron handler failed: %s", exc)


__all__ = [
    "DecommissionState",
    "build_graph",
    "graph",
    "state_from_event",
    "thread_id_from_event",
    "cron_fire",
    "healthz",
    "WITNESS_MIN",
    "VALID_TRIGGER_REASONS",
    "URBAN_MINING_DOC",
]
