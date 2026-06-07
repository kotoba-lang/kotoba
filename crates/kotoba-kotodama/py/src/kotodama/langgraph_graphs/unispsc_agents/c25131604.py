# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25131604 — Rescue Heli (segment 25).

This bespoke implementation handles emergency rescue helicopter dispatch workflows,
verifying mission parameters, pre-flight mechanical readiness, and specialized
crew availability.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25131604"
UNISPSC_TITLE = "Rescue Heli"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25131604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    mission_id: str
    fuel_reserve_pct: int
    crew_manifest_ready: bool
    avionics_status: str
    target_lz_id: str


def validate_mission_profile(state: State) -> dict[str, Any]:
    """Analyzes the incoming rescue request for mission ID and destination."""
    inp = state.get("input") or {}
    m_id = inp.get("mission_id", "RESCUE-DELTA-01")
    lz_id = inp.get("lz", "LZ-BASE")
    return {
        "log": [f"{UNISPSC_CODE}:validate_mission_profile: targeting {lz_id}"],
        "mission_id": m_id,
        "target_lz_id": lz_id,
    }


def verify_airframe_readiness(state: State) -> dict[str, Any]:
    """Simulates pre-flight check of fuel, crew, and avionics."""
    return {
        "log": [f"{UNISPSC_CODE}:verify_airframe_readiness: systems check nominal"],
        "fuel_reserve_pct": 95,
        "crew_manifest_ready": True,
        "avionics_status": "GREEN",
    }


def execute_scramble(state: State) -> dict[str, Any]:
    """Confirms final dispatch and emits mission authorization."""
    ready = all([
        state.get("fuel_reserve_pct", 0) > 25,
        state.get("crew_manifest_ready"),
        state.get("avionics_status") == "GREEN"
    ])
    return {
        "log": [f"{UNISPSC_CODE}:execute_scramble: {'approved' if ready else 'rejected'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission_id": state.get("mission_id"),
            "lz": state.get("target_lz_id"),
            "status": "DISPATCHED" if ready else "GROUNDED",
            "ok": ready,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_mission_profile)
_g.add_node("verify", verify_airframe_readiness)
_g.add_node("scramble", execute_scramble)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "scramble")
_g.add_edge("scramble", END)

graph = _g.compile()
