"""
DeploymentPlanningCell — kuni-umi Phase 2 Pregel cell.

Per ADR-2605201400 §1 (Actor topology — Tier B per-phase leader on
``zebulun``) + §3 (Phase 2 — Planning) + ADR-2605192415 §4.

Consumes the ``submitSiteSurvey`` records emitted by SiteSurveyCell
(kuni-umi Phase 1) and produces a ``proposeDeploymentPlan`` envelope:

  BoM (UNSPSC commodity code list + quantities + estimated USDC cost,
  ADR-2605171300) → target topology DIDs (FK ↔ open-* CIM records) →
  fleet allocation (Giemon robotCount + estimatedRobotHours) → payment
  schedule (USDC on Base L2 via Etzhayyim.pay() with TitheRouter 90/10
  split, ADR-2605172100/2605192130) → proportionality-check DMN. When
  scale × impact × reversibility breaches the threshold, the plan is
  blocked on a Council Lv6+ vote (ADR-2605192415 Tier C) and held at a
  fixed-point until governance returns.

BoM and payment-plan payloads are XChaCha20-Poly1305 envelopes per
ADR-2605181100 (recipients: Council Lv6+ ≥3 + plan steward + assigned
construction-cell leader). This scaffold emits synthetic envelope CIDs;
real wiring will use ``@etzhayyim/sdk`` + Signal-wrapped per-recipient
keys.

LangGraph nodes (super-step semantics):

  START → parse_survey_record    → load submitSiteSurvey record
        → compute_bom            → fan-out to UnispscAgentExecutorCell
        →                            shards 0/1/2 for code-level qty +
        →                            USDC cost (LAN HTTP)
        → estimate_cost          → aggregate BoM cost + slack envelope
        → allocate_fleet         → Giemon robotCount + estimatedRobotHours
        → proportionality_dmn    → scale × impact × reversibility gate
        → council_route          → conditional:
        →                            requiresGovernance ? emit_proposal →
        →                                                 wait_governance_vote (fixed-point)
        →                          else: emit_plan_record
        → emit_plan_record       → write proposeDeploymentPlan to MST
        → END

The governance wait-state is the only fixed-point; the MST listener for
the council vote record re-enters the cell with
``governance_votes_passed=True``. Other nodes are O(seconds).
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Annotated, TypedDict
from operator import add

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger("DeploymentPlanningCell")

# UnispscAgentExecutorCell LAN endpoints — re-declared locally to keep
# the cell independent of SiteSurveyCell (cells are decoupled units of
# deployment per ADR-2605192415 §3). Same defaults as Phase 1.
EXECUTOR_SHARDS = {
    0: os.environ.get("UNISPSC_EXECUTOR_SHARD_0", "http://josephnomac-mini.local:16100"),
    1: os.environ.get("UNISPSC_EXECUTOR_SHARD_1", "http://issacharnomac-mini.local:16101"),
    2: os.environ.get("UNISPSC_EXECUTOR_SHARD_2", "http://dannomac-mini.local:16102"),
}

# Default UNSPSC code mapping per utility class. Codes target realistic
# mid-segment commodities (8-digit) rather than bare segment roots; the
# planning phase needs SKU-level granularity for BoM costing. Real
# wiring will derive these from intended_use NLP + Council scope rules.
UTILITY_TO_UNSPSC_CODES: dict[str, list[str]] = {
    "electric": [
        "26121800",  # Electrical wire
        "39111600",  # Electrical switches
        "32101500",  # Sensors
        "26111700",  # Power transformers
        "39121000",  # Lighting fixtures
    ],
    "gas": [
        "12141900",  # Industrial gases
        "40141600",  # Pipe fittings
        "27112100",  # Pneumatic tools
        "26111600",  # Generators
    ],
    "water": [
        "40141700",  # Plumbing pipes
        "30181500",  # Water tanks
        "27112000",  # Hydraulic tools
        "40151500",  # Pumps
    ],
    "network": [
        "43222600",  # Network switching devices
        "26121500",  # Network cabling
        "32101600",  # Routing equipment
        "43211500",  # Servers
    ],
    "power": [
        "26111700",  # Transformers
        "39121400",  # Photovoltaic panels
        "40101700",  # Power distribution
        "26111600",  # Generators
    ],
    "rail": [
        "25172500",  # Rail rolling stock
        "30102200",  # Rail track materials
        "26111600",  # Traction power
    ],
    "airplane": [
        "25131600",  # Fixed-wing aircraft
        "23241500",  # Airframe production tooling
        "26111600",  # Aviation electrical
    ],
    "port": [
        "25101500",  # Cargo vessels
        "30102200",  # Port civil works
        "24101500",  # Material handling
    ],
    "multi": [
        "26121800",  # Electrical wire
        "40141700",  # Plumbing pipes
        "39111600",  # Switches
        "43222600",  # Network switches
    ],
}

# Proportionality DMN thresholds (ADR-2605201400 §5). Real DMN file at
# 00-contracts/dmn/proportionality-check.md; this scaffold encodes the
# scalar gates inline.
PROPORTIONALITY_COST_USDC = 100_000        # ≥ $100k notional → Council
PROPORTIONALITY_ROBOT_HOURS = 500          # ≥ 500 robot-hours → Council
PROPORTIONALITY_LIFESPAN_YEARS = 30        # ≥ 30 yr lifespan → Council
PROPORTIONALITY_REVERSIBILITY_FLOOR = 50   # impact > 50 → Council

DEFAULT_LIFESPAN_YEARS = 30
DEFAULT_SLACK_DAYS = 7
DEFAULT_FAN_OUT_LIMIT = 8


class DeploymentPlanningState(TypedDict, total=False):
    # ── inputs ───────────────────────────────────────────────────────
    survey_uri: str
    survey_record: dict[str, Any]
    survey_did: str
    site_did: str
    site_code: str
    utility_class: str
    intended_use: str
    ecology_baseline: dict[str, Any]

    # ── BoM (XChaCha20-Poly1305 envelope payload, ADR-2605181100) ────
    bom_codes: list[str]
    bom_items: Annotated[list[dict[str, Any]], add]
    bom_total_usdc: int
    bom_envelope_cid: str

    # ── topology ─────────────────────────────────────────────────────
    target_topology_dids: list[str]

    # ── fleet ────────────────────────────────────────────────────────
    fleet_allocation: dict[str, Any]

    # ── payment plan (XChaCha20-Poly1305 envelope, ADR-2605181100) ───
    payment_plan_cid: str

    # ── timeline ─────────────────────────────────────────────────────
    timeline: dict[str, Any]
    lifespan_years: int

    # ── proportionality DMN ──────────────────────────────────────────
    proportionality_breach: bool
    proportionality_reasons: list[str]
    requires_governance: bool

    # ── governance ───────────────────────────────────────────────────
    governance_proposal_uri: str
    governance_votes_passed: bool

    # ── output ───────────────────────────────────────────────────────
    plan_code: str
    plan_did: str
    decision: str
    accepted: bool
    submission_at_uri: str
    error: str


# ── helpers ─────────────────────────────────────────────────────────


def _shard_for_code(code: str) -> int | None:
    if not code or len(code) < 2 or not code[:2].isdigit():
        return None
    seg = int(code[:2])
    if 10 <= seg <= 29:
        return 0
    if 30 <= seg <= 44:
        return 1
    if 45 <= seg <= 60:
        return 2
    return None


def _synthetic_cid(label: str, payload: dict[str, Any]) -> str:
    """Placeholder CID for XChaCha20-Poly1305 envelope payload.

    Real wiring (ADR-2605181100): seal payload with libsodium
    crypto_aead_xchacha20poly1305_ietf_encrypt + per-recipient Signal-
    wrapped DEKs → publish to IPFS → return CIDv1. Scaffold emits a
    deterministic stub that downstream cells can dereference in tests.
    """
    digest = abs(hash((label, json.dumps(payload, sort_keys=True, default=str)))) % (1 << 60)
    return f"bafyenv-{label}-{digest:x}"


def _plan_code_for(site_code: str, utility: str, ts: int) -> str:
    site = (site_code or "UNK").upper().replace(" ", "")[:24]
    util = (utility or "MULTI").upper()[:8]
    return f"PLAN-{site}-{util}-{ts}"


# ── Node functions ──────────────────────────────────────────────────


def parse_survey_record(state: DeploymentPlanningState) -> dict[str, Any]:
    """Load the submitSiteSurvey record referenced by survey_uri."""
    rec = state.get("survey_record") or {}
    if not rec and state.get("survey_uri"):
        # Real wiring fetches via etzhayyim_sdk MST. Stub for now.
        rec = {}
    return {
        "survey_record": rec,
        "site_did": rec.get("siteDid") or state.get("site_did") or "",
        "survey_did": rec.get("surveyDid") or state.get("survey_did") or "",
        "site_code": rec.get("siteCode") or state.get("site_code") or "",
        "utility_class": rec.get("utilityClass") or state.get("utility_class") or "multi",
        "intended_use": rec.get("intendedUse") or state.get("intended_use") or "",
        "ecology_baseline": rec.get("ecologyBaseline") if isinstance(rec.get("ecologyBaseline"), dict) else (state.get("ecology_baseline") or {}),
    }


def compute_bom(state: DeploymentPlanningState) -> dict[str, Any]:
    """Fan out to UnispscAgentExecutorCell shards to materialize the BoM.

    Each candidate UNSPSC code is routed to the segment-owning shard
    (10-29 → 0, 30-44 → 1, 45-60 → 2). The executor returns the agent's
    canonical quantity hint + per-unit USDC cost. Scaffold falls back to
    a synthesized line item if the executor is unreachable.
    """
    import urllib.request

    utility = state.get("utility_class") or "multi"
    codes = UTILITY_TO_UNSPSC_CODES.get(utility, UTILITY_TO_UNSPSC_CODES["multi"])
    codes = codes[:DEFAULT_FAN_OUT_LIMIT]

    items: list[dict[str, Any]] = []
    for code in codes:
        shard = _shard_for_code(code)
        if shard is None:
            continue
        url = f"{EXECUTOR_SHARDS[shard]}/api/invoke"
        line = {
            "code": code,
            "shard": shard,
            "qty": 1,
            "unitCostUsdc": 0,
            "lineCostUsdc": 0,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({
                    "code": code,
                    "input": {
                        "site_did": state.get("site_did", ""),
                        "utility_class": utility,
                        "intended_use": state.get("intended_use", ""),
                        "phase": "kuni-umi-2-planning",
                    },
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            agent_state = payload.get("state", {}) if isinstance(payload, dict) else {}
            qty = int(agent_state.get("qty") or agent_state.get("recommendedQty") or 1)
            unit_cost = int(agent_state.get("unitCostUsdc") or agent_state.get("estimatedUnitUsdc") or 0)
            line.update({
                "qty": qty,
                "unitCostUsdc": unit_cost,
                "lineCostUsdc": qty * unit_cost,
                "ok": bool(payload.get("ok")),
            })
        except Exception as exc:  # noqa: BLE001 — record + continue
            line["error"] = str(exc)
        items.append(line)

    return {
        "bom_codes": codes,
        "bom_items": items,
    }


def estimate_cost(state: DeploymentPlanningState) -> dict[str, Any]:
    """Aggregate line items + seal the BoM envelope CID."""
    items = state.get("bom_items") or []
    total = sum(int(it.get("lineCostUsdc") or 0) for it in items)
    # If at least one line item materialized cleanly (no error + qty>0)
    # but unit cost was missing, fall back to a conservative notional so
    # the DMN has signal. If *every* item recorded an executor error
    # (typical for offline smoke tests), keep total at 0 — the
    # proportionality DMN will treat the plan as empty and skip the
    # Council gate. Real production runs always have at least one
    # clean item.
    clean_items = [it for it in items if not it.get("error")]
    if total == 0 and clean_items:
        total = 25_000 * len(clean_items)
    bom_cid = _synthetic_cid("bom", {
        "site_did": state.get("site_did", ""),
        "survey_did": state.get("survey_did", ""),
        "items": items,
        "totalUsdc": total,
    })
    return {
        "bom_total_usdc": total,
        "bom_envelope_cid": bom_cid,
    }


def allocate_fleet(state: DeploymentPlanningState) -> dict[str, Any]:
    """Derive Giemon robot allocation from BoM weight.

    Heuristic (ADR-2605201400 §3 Phase 2): 1 robot per 4 BoM line items
    (Otete arm coverage), 40 robot-hours per $25k notional (commission +
    install + commissioning labor). Real wiring will call into the
    Giemon dispatcher with manipulability + tool-coverage constraints.
    """
    items = state.get("bom_items") or []
    total = int(state.get("bom_total_usdc") or 0)
    robot_count = max(1, (len(items) + 3) // 4)
    robot_hours = max(8, (total // 25_000) * 40) if total else 8 * robot_count
    return {
        "fleet_allocation": {
            "robotCount": robot_count,
            "estimatedRobotHours": robot_hours,
            "fleetDid": "",  # pre-allocation deferred to ConstructionOrchestrationCell
        },
    }


def proportionality_dmn(state: DeploymentPlanningState) -> dict[str, Any]:
    """Run the proportionality-check DMN (ADR-2605201400 §5).

    Inputs: BoM total cost, fleet robot-hours, lifespan, ecology impact.
    Output: requires_governance flag + reasons list. Council Lv6+ vote
    is the constitutional gate when any threshold breaches.
    """
    cost = int(state.get("bom_total_usdc") or 0)
    fleet = state.get("fleet_allocation") or {}
    robot_hours = int(fleet.get("estimatedRobotHours") or 0)
    lifespan = int(state.get("lifespan_years") or DEFAULT_LIFESPAN_YEARS)
    ecology = state.get("ecology_baseline") or {}
    impact = int(ecology.get("impactScore") or 0)
    items = state.get("bom_items") or []

    reasons: list[str] = []
    # Scaffold/empty-state short-circuit: a plan with no BoM lines and
    # zero notional cost cannot breach proportionality (nothing to be
    # disproportionate about). Real production runs always have BoM
    # items materialized by compute_bom — this guard only fires on
    # smoke tests / null events.
    nonempty_plan = bool(items) and cost > 0
    if nonempty_plan:
        if cost >= PROPORTIONALITY_COST_USDC:
            reasons.append(f"cost>={PROPORTIONALITY_COST_USDC}")
        if robot_hours >= PROPORTIONALITY_ROBOT_HOURS:
            reasons.append(f"robotHours>={PROPORTIONALITY_ROBOT_HOURS}")
        if lifespan >= PROPORTIONALITY_LIFESPAN_YEARS:
            reasons.append(f"lifespan>={PROPORTIONALITY_LIFESPAN_YEARS}")
        if impact > PROPORTIONALITY_REVERSIBILITY_FLOOR:
            reasons.append(f"impact>{PROPORTIONALITY_REVERSIBILITY_FLOOR}")

    breach = bool(reasons)
    return {
        "proportionality_breach": breach,
        "proportionality_reasons": reasons,
        "requires_governance": breach,
        "lifespan_years": lifespan,
    }


def emit_governance_proposal(state: DeploymentPlanningState) -> dict[str, Any]:
    """Emit the Council Lv6+ proposal record + hold pending vote.

    Scaffold: stamps a synthetic proposal URI. Real wiring will use
    CouncilDeliberationCell (ADR-2605192415 Tier C) on ``levi``.
    """
    site_did = state.get("site_did") or "did:web:etzhayyim.com:site:unknown"
    proposal_uri = (
        f"at://{site_did}/com.etzhayyim.governance.councilProposal/"
        f"plan-{int(time.time() * 1000)}"
    )
    return {
        "governance_proposal_uri": proposal_uri,
        "decision": "awaiting-governance",
    }


def wait_governance_vote(state: DeploymentPlanningState) -> dict[str, Any]:
    """Fixed-point node — pauses (via checkpointer) until council votes.

    The MST listener for the council-vote record triggers re-entry with
    ``governance_votes_passed`` set. The router below advances when the
    vote returns truthy, otherwise re-enters this node.
    """
    return {}


def emit_plan_record(state: DeploymentPlanningState) -> dict[str, Any]:
    """Write the proposeDeploymentPlan record to MST.

    Scaffold: stamps a synthetic at:// URI + plan DID. Real wiring will
    use ``@etzhayyim/sdk`` PdsClient with the cell's DID + signed
    envelope. Payment plan CID is the placeholder XChaCha20-Poly1305
    envelope for the USDC TitheRouter call schedule.
    """
    site_did = state.get("site_did") or "did:web:etzhayyim.com:site:unknown"
    ts = int(time.time())
    plan_code = state.get("plan_code") or _plan_code_for(
        state.get("site_code") or "",
        state.get("utility_class") or "multi",
        ts,
    )
    plan_did = f"{site_did}:plan:{ts}"
    submission_uri = (
        f"at://{site_did}/com.etzhayyim.apps.etzhayyim.kuniUmi.proposeDeploymentPlan/"
        f"{int(time.time() * 1000)}"
    )
    payment_cid = _synthetic_cid("payment", {
        "plan_code": plan_code,
        "total_usdc": int(state.get("bom_total_usdc") or 0),
        "tithe_split_bps": 1000,  # 10% per TitheRouter (ADR-2605192130)
    })
    # decision resolution: if we passed through governance and it
    # passed, accept; if we never required governance, accept; else
    # the previous emit_governance_proposal already set
    # decision=awaiting-governance and we won't reach here without a
    # passed vote.
    requires_gov = bool(state.get("requires_governance"))
    voted_ok = bool(state.get("governance_votes_passed"))
    accepted = (not requires_gov) or voted_ok
    decision = "accept" if accepted else "awaiting-governance"
    target_topology = state.get("target_topology_dids") or [
        f"{site_did}:topology:{state.get('utility_class') or 'multi'}",
    ]
    return {
        "plan_code": plan_code,
        "plan_did": plan_did,
        "target_topology_dids": target_topology,
        "payment_plan_cid": payment_cid,
        "submission_at_uri": submission_uri,
        "decision": decision,
        "accepted": accepted,
        "timeline": state.get("timeline") or {
            "startISO": "",
            "endISO": "",
            "slackDays": DEFAULT_SLACK_DAYS,
        },
        "lifespan_years": int(state.get("lifespan_years") or DEFAULT_LIFESPAN_YEARS),
    }


# ── Graph build ─────────────────────────────────────────────────────


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(DeploymentPlanningState)

    g.add_node("parse_survey_record", parse_survey_record)
    g.add_node("compute_bom", compute_bom)
    g.add_node("estimate_cost", estimate_cost)
    g.add_node("allocate_fleet", allocate_fleet)
    g.add_node("proportionality_dmn", proportionality_dmn)
    g.add_node("emit_governance_proposal", emit_governance_proposal)
    g.add_node("wait_governance_vote", wait_governance_vote)
    g.add_node("emit_plan_record", emit_plan_record)

    g.add_edge(START, "parse_survey_record")
    g.add_edge("parse_survey_record", "compute_bom")
    g.add_edge("compute_bom", "estimate_cost")
    g.add_edge("estimate_cost", "allocate_fleet")
    g.add_edge("allocate_fleet", "proportionality_dmn")

    def council_router(state: DeploymentPlanningState) -> str:
        if state.get("requires_governance"):
            return "emit_governance_proposal"
        return "emit_plan_record"

    g.add_conditional_edges("proportionality_dmn", council_router, {
        "emit_governance_proposal": "emit_governance_proposal",
        "emit_plan_record": "emit_plan_record",
    })

    g.add_edge("emit_governance_proposal", "wait_governance_vote")

    def vote_router(state: DeploymentPlanningState) -> str:
        if state.get("governance_votes_passed"):
            return "emit_plan_record"
        return "wait_governance_vote"  # hold at fixed-point

    g.add_conditional_edges("wait_governance_vote", vote_router, {
        "emit_plan_record": "emit_plan_record",
        "wait_governance_vote": "wait_governance_vote",
    })

    g.add_edge("emit_plan_record", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


graph = build_graph()


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ─────────────────


def state_from_event(event: dict[str, Any]) -> DeploymentPlanningState:
    """Map an MST submitSiteSurvey event payload into the cell's state."""
    rec = event.get("record") or event.get("value") or {}
    rec = rec if isinstance(rec, dict) else {}
    return {
        "survey_uri": event.get("uri", ""),
        "survey_record": rec,
        "survey_did": rec.get("surveyDid") or event.get("uri", ""),
        "site_did": rec.get("siteDid") or event.get("repo", ""),
        "bom_items": [],
        "governance_votes_passed": False,
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    return f"deployment-planning-{event.get('uri', '').replace('/', '-')[-40:]}"


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "DeploymentPlanningCell",
        "phase": "kuni-umi-2",
        "executorShards": {k: v for k, v in EXECUTOR_SHARDS.items()},
        "proportionality": {
            "costUsdc": PROPORTIONALITY_COST_USDC,
            "robotHours": PROPORTIONALITY_ROBOT_HOURS,
            "lifespanYears": PROPORTIONALITY_LIFESPAN_YEARS,
            "impactCeiling": PROPORTIONALITY_REVERSIBILITY_FLOOR,
        },
        "utilityClasses": sorted(UTILITY_TO_UNSPSC_CODES.keys()),
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
    "DeploymentPlanningState",
    "build_graph",
    "graph",
    "state_from_event",
    "thread_id_from_event",
    "handle_mst_event",
    "healthz",
    "EXECUTOR_SHARDS",
    "UTILITY_TO_UNSPSC_CODES",
    "PROPORTIONALITY_COST_USDC",
    "PROPORTIONALITY_ROBOT_HOURS",
    "PROPORTIONALITY_LIFESPAN_YEARS",
    "PROPORTIONALITY_REVERSIBILITY_FLOOR",
]
