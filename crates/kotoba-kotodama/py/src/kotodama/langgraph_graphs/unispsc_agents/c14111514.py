# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14111514 — File System (segment 14).

Bespoke graph for managing physical file systems and organizational structures
within the Paper Materials and Products domain. This agent automates the
design of indexing strategies and folder allocation for office environments.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111514"
UNISPSC_TITLE = "File System"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111514"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for File System organization
    index_strategy: str
    folder_count: int
    label_format: str
    is_archival: bool
    system_status: str


def plan_indexing(state: State) -> dict[str, Any]:
    """Analyzes requirements to determine the optimal indexing method."""
    inp = state.get("input") or {}
    strategy = inp.get("preferred_strategy", "chronological")
    archival = inp.get("archival_duty", False)

    return {
        "log": [f"{UNISPSC_CODE}:plan_indexing"],
        "index_strategy": strategy,
        "is_archival": archival,
        "system_status": "indexing_defined",
    }


def provision_containers(state: State) -> dict[str, Any]:
    """Calculates the physical folder capacity needed for the system."""
    inp = state.get("input") or {}
    document_count = inp.get("expected_items", 500)
    # Average 50 sheets per folder
    needed_folders = (document_count // 50) + (1 if document_count % 50 > 0 else 0)

    return {
        "log": [f"{UNISPSC_CODE}:provision_containers"],
        "folder_count": needed_folders,
        "system_status": "capacity_allocated",
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final configuration for the file system deployment."""
    strategy = state.get("index_strategy", "standard")
    folders = state.get("folder_count", 0)

    # Determine label format based on strategy
    label_fmt = "ISO-8601" if strategy == "chronological" else "Alpha-Numeric"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "label_format": label_fmt,
        "system_status": "ready",
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "configuration": {
                "strategy": strategy,
                "folders_required": folders,
                "labeling": label_fmt,
                "archival": state.get("is_archival", False)
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("plan_indexing", plan_indexing)
_g.add_node("provision_containers", provision_containers)
_g.add_node("finalize_manifest", finalize_manifest)

_g.add_edge(START, "plan_indexing")
_g.add_edge("plan_indexing", "provision_containers")
_g.add_edge("provision_containers", "finalize_manifest")
_g.add_edge("finalize_manifest", END)

graph = _g.compile()
