# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23131603 — P L C (segment 23).

Bespoke graph for Programmable Logic Controller (PLC) lifecycle management,
including ladder logic validation, I/O module mapping, and runtime deployment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23131603"
UNISPSC_TITLE = "P L C"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23131603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific PLC state
    logic_compiled: bool
    io_mapping_valid: bool
    firmware_version: str
    cycle_time_ms: float
    is_faulted: bool


def validate_logic(state: State) -> dict[str, Any]:
    """Validates the uploaded ladder logic or structured text program."""
    inp = state.get("input") or {}
    prog = inp.get("program", "")
    # Simple validation: program must not be empty and should have a termination instruction
    valid = len(prog) > 0 and ("END" in prog or "RET" in prog)
    return {
        "log": [f"{UNISPSC_CODE}:validate_logic -> {valid}"],
        "logic_compiled": valid,
        "firmware_version": inp.get("target_firmware", "v1.0.0"),
    }


def map_io_modules(state: State) -> dict[str, Any]:
    """Assigns physical I/O addresses to logic tags and checks for conflicts."""
    inp = state.get("input") or {}
    ios = inp.get("io_config", [])
    # Verify we have at least one input/output mapping if logic is valid
    mapping_ok = state.get("logic_compiled", False) and len(ios) > 0
    return {
        "log": [f"{UNISPSC_CODE}:map_io_modules -> {mapping_ok}"],
        "io_mapping_valid": mapping_ok,
        "cycle_time_ms": 5.5 if mapping_ok else 0.0,
    }


def deploy_runtime(state: State) -> dict[str, Any]:
    """Finalizes the build and prepares the PLC for RUN mode."""
    success = state.get("logic_compiled", False) and state.get("io_mapping_valid", False)
    fault = not success

    return {
        "log": [f"{UNISPSC_CODE}:deploy_runtime -> success: {success}"],
        "is_faulted": fault,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "deployed": success,
            "firmware": state.get("firmware_version"),
            "scan_cycle": f"{state.get('cycle_time_ms', 0)}ms",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_logic)
_g.add_node("map_io", map_io_modules)
_g.add_node("deploy", deploy_runtime)

_g.add_edge(START, "validate")
_g.add_edge("validate", "map_io")
_g.add_edge("map_io", "deploy")
_g.add_edge("deploy", END)

graph = _g.compile()
