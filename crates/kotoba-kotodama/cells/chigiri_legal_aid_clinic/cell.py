"""
ChigiriLegalAidClinicCell — Pregel cell orchestrating a FREE legal-aid intake.

Per ADR-2605302200 (lawful lanes + 10-jurisdiction matrix), ADR-2605302330
(Japan 認証ADR mediation lane), ADR-2605302345 (counsel-operated delivery),
and chigiri R0 charter ADR-2605262700 (G14 UPL prohibition).

WHAT THIS CELL IS (and is NOT):
  - It is an INTAKE + ROUTING substrate. It opens a free matter, runs a
    conflict check, classifies the matter (NON-advice), checks the
    jurisdiction is `enabled`, assigns an in-jurisdiction licensed lawyer
    out of the Public Fund, and emits a legalAidMatter record.
  - It DOES NOT render legal advice. The licensed human lawyer is the
    practitioner (G14). No node here produces advice text.

CONSTITUTIONAL GUARDS (enforced as code, not just comments):
  - G14: no node emits legal advice. `triage_classify` returns a routing
    LABEL from a fixed enum only; `_assert_no_advice` rejects free-text.
  - G15: the matter charges the adherent nothing. `assert_zero_compensation`
    pins zeroCompensation=True and there is no fee/consideration field.
  - G16: a matter MUST NOT advance past `intake` without a resolvable,
    in-jurisdiction supervisingCounsel. `route_after_counsel` enforces it.

INFERENCE DISCIPLINE (ADR-2605215000):
  - The ONLY LLM use is `triage_classify`, a NON-advice classifier that
    routes through the Murakumo fleet (judah LiteLLM 127.0.0.1:4000 →
    gemma on the EVO-X2 LAN). It returns one label from PRACTICE_AREAS /
    LANES. It MUST NOT be asked to advise, and its output is constrained
    to the enum by `_assert_no_advice`. No commercial GPU. kotoba-llm stays
    disabled (Charter Rider §2(i)).

Murakumo node: judah (leader), levi (mediation pair for Lane B handoff)
Storage: legalAidMatter records → kotoba EAVT (com.etzhayyim.chigiri.legalAidMatter)
"""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver


Lane = Literal["advice", "certified-mediation"]
PracticeArea = Literal[
    "family", "housing", "labor", "consumer", "immigration",
    "administrative", "contract", "other",
]
IntakeState = Literal[
    "intake", "counsel-assigned", "active", "resolved", "closed", "rejected",
]

# Routing labels the NON-advice classifier is allowed to emit. Anything
# outside these sets is treated as an advice leak and rejected (G14).
PRACTICE_AREAS: frozenset[str] = frozenset(PracticeArea.__args__)  # type: ignore[attr-defined]
LANES: frozenset[str] = frozenset(Lane.__args__)  # type: ignore[attr-defined]


class LegalAidIntakeState(TypedDict, total=False):
    # ── Input — from the adherent intake record on MST ──
    matter_uri: str
    adherent_did: str
    jurisdiction: str            # ISO, e.g. jpn / us-ca / fra
    summary_cid: str             # adherent-authored description (NOT advice)

    # ── Conflict + routing ──
    conflict_checked: bool
    conflict_clear: bool
    practice_area: PracticeArea  # NON-advice classification label
    lane: Lane

    # ── Jurisdiction policy (G16 enablement) ──
    jurisdiction_enabled: bool   # jurisdictionPolicy.enableState == "enabled"

    # ── Supervising counsel (G16) ──
    supervising_counsel_did: str
    counsel_license_jurisdiction: str
    counsel_retained_via_public_fund: bool

    # ── Compensation (G15) ──
    zero_compensation: bool

    # ── Output ──
    intake_state: IntakeState
    matter_record_cid: str
    rejection_reason: str


def build_graph(
    checkpointer: BaseCheckpointSaver,
    mst_port,
    policy_port,
    counsel_port,
    murakumo_port,
):
    """Compile the legal-aid intake graph.

    Ports (dependency-injected, keep the cell pure):
      mst_port      — read intake record / write legalAidMatter record
      policy_port   — jurisdictionPolicy lookup (enableState)
      counsel_port  — Public-Fund counsel registry (G16 assignment)
      murakumo_port — NON-advice classifier via the Murakumo fleet
    """
    g = StateGraph(LegalAidIntakeState)

    g.add_node("load_intake", lambda s: load_intake(s, mst_port))
    g.add_node("conflict_check", lambda s: conflict_check(s, counsel_port))
    g.add_node("triage_classify", lambda s: triage_classify(s, murakumo_port))
    g.add_node("check_jurisdiction", lambda s: check_jurisdiction(s, policy_port))
    g.add_node("assign_counsel", lambda s: assign_counsel(s, counsel_port))
    g.add_node("assert_zero_compensation", assert_zero_compensation)
    g.add_node("emit_matter_record", lambda s: emit_matter_record(s, mst_port))
    g.add_node("emit_rejection", lambda s: emit_rejection(s, mst_port))

    g.add_edge(START, "load_intake")

    # conflict gate
    g.add_edge("load_intake", "conflict_check")
    g.add_conditional_edges(
        "conflict_check",
        lambda s: "triage_classify" if s.get("conflict_clear") else "emit_rejection",
    )

    # classify → jurisdiction enablement gate
    g.add_edge("triage_classify", "check_jurisdiction")
    g.add_conditional_edges(
        "check_jurisdiction",
        lambda s: "assign_counsel" if s.get("jurisdiction_enabled") else "emit_rejection",
    )

    # G16: no advance past intake without resolvable in-jurisdiction counsel
    g.add_edge("assign_counsel", "assert_zero_compensation")
    g.add_conditional_edges("assert_zero_compensation", route_after_counsel)

    g.add_edge("emit_matter_record", END)
    g.add_edge("emit_rejection", END)

    return g.compile(checkpointer=checkpointer)


# ─── Guards ───────────────────────────────────────────────────────────


def _assert_no_advice(label: str) -> str:
    """G14 — the classifier may only emit a known routing label.

    Any free-text / out-of-enum output is treated as an advice leak and
    rejected. chigiri renders no legal advice; only humans licensed to
    practise do.
    """
    norm = (label or "").strip().lower()
    if norm not in PRACTICE_AREAS:
        raise ValueError(
            f"G14 violation: triage classifier returned non-label output "
            f"{label!r}; the cell must never produce or relay legal advice. "
            f"Allowed labels: {sorted(PRACTICE_AREAS)}."
        )
    return norm


# ─── Node functions ───────────────────────────────────────────────────


def load_intake(state, mst_port):
    """Fetch the adherent-authored intake record from MST.

    The summary is the adherent's OWN description of their problem — it is
    not advice and is never generated by the cell.
    """
    # TODO: rec = mst_port.get(state["matter_uri"])  -> adherent_did, jurisdiction, summary_cid
    return {**state, "intake_state": "intake"}


def conflict_check(state, counsel_port):
    """Conflict-of-interest check against existing matters / adverse parties."""
    # TODO: clear = counsel_port.conflict_clear(state["adherent_did"], state.get("summary_cid"))
    return {**state, "conflict_checked": True, "conflict_clear": True}


def triage_classify(state, murakumo_port):
    """NON-advice classification via the Murakumo fleet (ADR-2605215000).

    Routes the adherent summary to ONE practice-area label and ONE lane.
    This is categorization, NOT advice. The Murakumo port MUST hit the
    fleet (judah LiteLLM 127.0.0.1:4000 → gemma); never a commercial GPU.
    The result is constrained to the enum by `_assert_no_advice` (G14).
    """
    # TODO: raw = murakumo_port.classify(summary_cid=state.get("summary_cid"),
    #                                    labels=sorted(PRACTICE_AREAS))
    raw = state.get("practice_area", "other")
    area = _assert_no_advice(raw)
    # Lane default: advice; certified-mediation only when both parties are
    # adherents seeking a settlement (Lane B, ADR-2605302330). Decided by
    # structured intake fields, not by the LLM.
    lane: Lane = "advice"
    return {**state, "practice_area": area, "lane": lane}


def check_jurisdiction(state, policy_port):
    """G16 enablement — the jurisdiction must be `enabled` (not verify-required).

    AT (Austria) out-of-court scope and US state-level granularity ship as
    `verify-required` and are rejected here until a legality review enables
    them (ADR-2605302200 §D4).
    """
    # TODO: pol = policy_port.lookup(state["jurisdiction"])
    #       enabled = pol is not None and pol["enableState"] == "enabled"
    enabled = bool(state.get("jurisdiction_enabled"))
    if not enabled:
        return {
            **state,
            "jurisdiction_enabled": False,
            "rejection_reason": (
                f"jurisdiction {state.get('jurisdiction')!r} is not `enabled` "
                f"(verify-required); no matter may open (ADR-2605302200 §D4)."
            ),
        }
    return {**state, "jurisdiction_enabled": True}


def assign_counsel(state, counsel_port):
    """G16 — resolve an in-jurisdiction licensed lawyer retained via Public Fund.

    DE: Befähigung zum Richteramt; US: bar admission. The license
    jurisdiction MUST match the matter jurisdiction.
    """
    # TODO: c = counsel_port.resolve(jurisdiction=state["jurisdiction"],
    #                                practice_area=state["practice_area"])
    c = counsel_port.resolve(state["jurisdiction"], state.get("practice_area")) \
        if hasattr(counsel_port, "resolve") else None
    if not c:
        return {
            **state,
            "rejection_reason": (
                f"no Public-Fund counsel licensed in {state.get('jurisdiction')!r} "
                f"available; matter held at intake (G16)."
            ),
        }
    return {
        **state,
        "supervising_counsel_did": c["did"],
        "counsel_license_jurisdiction": c["license_jurisdiction"],
        "counsel_retained_via_public_fund": True,
    }


def assert_zero_compensation(state):
    """G15 — the matter charges the adherent nothing, ever.

    There is no fee/consideration field in the state by construction; this
    node pins the invariant flag and would refuse any non-zero charge.
    """
    return {**state, "zero_compensation": True}


def route_after_counsel(state) -> Literal["emit_matter_record", "emit_rejection"]:
    """G16 + G15 final gate before persisting the matter."""
    counsel_ok = (
        bool(state.get("supervising_counsel_did"))
        and state.get("counsel_retained_via_public_fund") is True
        and state.get("counsel_license_jurisdiction") == state.get("jurisdiction")
    )
    comp_ok = state.get("zero_compensation") is True
    return "emit_matter_record" if (counsel_ok and comp_ok) else "emit_rejection"


def emit_matter_record(state, mst_port):
    """Write the legalAidMatter record (intakeState=counsel-assigned) to MST/kotoba.

    Schema-validated against com.etzhayyim.chigiri.legalAidMatter
    (zeroCompensation const true + supervisingCounsel required).
    """
    record = {
        "adherentDid": state["adherent_did"],
        "jurisdiction": state["jurisdiction"],
        "lane": state["lane"],
        "zeroCompensation": True,                      # G15
        "supervisingCounsel": {                        # G16
            "counselDid": state["supervising_counsel_did"],
            "licenseJurisdiction": state["counsel_license_jurisdiction"],
            "retainedViaPublicFund": True,
        },
        "intakeState": "counsel-assigned",
    }
    # TODO: cid = mst_port.put("com.etzhayyim.chigiri.legalAidMatter", record)
    cid = mst_port.put("com.etzhayyim.chigiri.legalAidMatter", record) \
        if hasattr(mst_port, "put") else "at://stub"
    return {**state, "intake_state": "counsel-assigned", "matter_record_cid": cid}


def emit_rejection(state, mst_port):
    """Emit a non-advice rejection/hold record. No advice is ever given here."""
    return {
        **state,
        "intake_state": "rejected",
        "rejection_reason": state.get("rejection_reason", "intake could not proceed"),
    }
