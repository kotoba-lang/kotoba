# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25151702 — Satellite (segment 25).

Bespoke graph for satellite mission planning and telemetry processing.
This agent handles orbit validation, payload health assessment, and
mission report generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25151702"
UNISPSC_TITLE = "Satellite"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25151702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Satellite
    orbit_profile: dict[str, Any]
    payload_status: str
    link_budget_db: float
    telemetry_lock: bool


def validate_orbit(state: State) -> dict[str, Any]:
    """Validates the target orbital parameters for the satellite mission."""
    inp = state.get("input") or {}
    altitude = inp.get("altitude_km", 550)
    inclination = inp.get("inclination_deg", 97.5)

    return {
        "log": [f"{UNISPSC_CODE}:validate_orbit"],
        "orbit_profile": {
            "altitude": altitude,
            "inclination": inclination,
            "type": "SSO" if 90 < inclination < 100 else "LEO"
        },
        "telemetry_lock": altitude > 0
    }


def assess_payload(state: State) -> dict[str, Any]:
    """Checks the health of the satellite bus and primary instruments."""
    is_locked = state.get("telemetry_lock", False)
    status = "NOMINAL" if is_locked else "MALFUNCTION"

    return {
        "log": [f"{UNISPSC_CODE}:assess_payload"],
        "payload_status": status,
        "link_budget_db": 12.4 if is_locked else -5.0
    }


def generate_report(state: State) -> dict[str, Any]:
    """Finalizes the satellite operation status and compiles the response."""
    profile = state.get("orbit_profile", {})
    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_status": state.get("payload_status"),
            "orbit_type": profile.get("type"),
            "signal_margin_db": state.get("link_budget_db"),
            "ok": state.get("payload_status") == "NOMINAL",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_orbit)
_g.add_node("assess", assess_payload)
_g.add_node("report", generate_report)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "report")
_g.add_edge("report", END)

graph = _g.compile()
