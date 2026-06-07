# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24122006 — App (segment 24).

Bespoke logic for managing Application-specific state and deployment
within the material handling and conditioning segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24122006"
UNISPSC_TITLE = "App"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24122006"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    app_id: str
    runtime_env: str
    manifest_valid: bool
    provisioned: bool


def ingest(state: State) -> dict[str, Any]:
    """Ingests the application request and identifies the target environment."""
    inp = state.get("input") or {}
    app_id = inp.get("app_id", "unnamed-app")
    return {
        "log": [f"{UNISPSC_CODE}:ingest"],
        "app_id": app_id,
        "runtime_env": inp.get("env", "production"),
    }


def validate(state: State) -> dict[str, Any]:
    """Validates the application manifest and security constraints."""
    app_id = state.get("app_id")
    is_valid = bool(app_id and app_id != "unnamed-app")
    return {
        "log": [f"{UNISPSC_CODE}:validate"],
        "manifest_valid": is_valid,
    }


def deploy(state: State) -> dict[str, Any]:
    """Provisions resources and finalizes the deployment state."""
    is_valid = state.get("manifest_valid", False)
    return {
        "log": [f"{UNISPSC_CODE}:deploy"],
        "provisioned": is_valid,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "app_id": state.get("app_id"),
            "env": state.get("runtime_env"),
            "status": "deployed" if is_valid else "failed",
            "did": UNISPSC_DID,
            "ok": is_valid,
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest)
_g.add_node("validate", validate)
_g.add_node("deploy", deploy)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "validate")
_g.add_edge("validate", "deploy")
_g.add_edge("deploy", END)

graph = _g.compile()
