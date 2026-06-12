# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25150000 — Spacecraft (segment 25).

Bespoke graph logic for spacecraft mission definition, launch simulation,
and orbital status monitoring.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25150000"
UNISPSC_TITLE = "Spacecraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25150000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    mission_profile: str
    propulsion_type: str
    orbit_altitude_km: int
    telemetry_status: str


def define_mission(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    profile = inp.get("profile", "low_earth_orbit")
    return {
        "log": [f"{UNISPSC_CODE}:define_mission: {profile}"],
        "mission_profile": profile,
        "propulsion_type": inp.get("propulsion", "chemical_bipropellant"),
    }


def simulate_launch(state: State) -> dict[str, Any]:
    profile = state.get("mission_profile", "unknown")
    altitude = 400 if profile == "low_earth_orbit" else 35786
    return {
        "log": [f"{UNISPSC_CODE}:simulate_launch: target altitude {altitude}km reached"],
        "orbit_altitude_km": altitude,
        "telemetry_status": "nominal",
    }


def monitor_systems(state: State) -> dict[str, Any]:
    status = state.get("telemetry_status", "offline")
    return {
        "log": [f"{UNISPSC_CODE}:monitor_systems: state is {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission": {
                "profile": state.get("mission_profile"),
                "altitude_km": state.get("orbit_altitude_km"),
                "propulsion": state.get("propulsion_type"),
            },
            "telemetry": status,
            "ok": status == "nominal",
        },
    }


_g = StateGraph(State)
_g.add_node("define_mission", define_mission)
_g.add_node("simulate_launch", simulate_launch)
_g.add_node("monitor_systems", monitor_systems)

_g.add_edge(START, "define_mission")
_g.add_edge("define_mission", "simulate_launch")
_g.add_edge("simulate_launch", "monitor_systems")
_g.add_edge("monitor_systems", END)

graph = _g.compile()
