"""
CharterAttestationRequestCell — Pregel cell for handling third-party
Charter Compliance attestation requests.

Per ADR-2605192230 (Three-Tier Enforcement) + ADR-2605192200 (Charter Rider v2.0).

Trigger: MST listener on `com.etzhayyim.apps.etzhayyim.charter-attestation-request`
Effect: LLM pre-analysis + dispatch to Council Lv6+ for deliberation
        → on quorum (≥3 signatures) → emit ChartersComplianceRegistry.attestNonAligned() tx

Murakumo node: naphtali (leader), asher (failover replica)
"""

from __future__ import annotations

from typing import Literal, TypedDict, Annotated
from operator import add

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver


class CharterAttestationRequestState(TypedDict, total=False):
    # Input — from MST event
    request_uri: str  # at:// URI of the charter-attestation-request record
    subject_address: str  # 0x... or DID
    subject_kind: Literal["address", "sbt_token_id"]
    subject_sbt_token_id: int | None
    alleged_violation: Literal[
        "rider.section_2a",  # weapons
        "rider.section_2b",  # speculative finance
        "rider.section_2c",  # surveillance capitalism
        "rider.section_2d",  # fossil fuel extraction (new)
        "rider.section_2e",  # specialist gatekeeping
        "rider.section_2f",  # multi-generational harm (v2.0)
        "rider.section_2g",  # strict individualist ontology (v2.0)
        "rider.section_2h",  # wellbecoming subordination (v2.0)
    ]
    evidence_uris: list[str]

    # LLM analysis
    llm_summary: str
    llm_rider_section_match_confidence: float  # 0.0 - 1.0
    llm_recommendation: Literal["forward_to_council", "request_more_evidence", "reject_unfounded"]
    llm_rationale: str

    # Council dispatch
    council_dispatch_uri: str  # at:// URI of the dispatch record sent to Lv6+
    council_signatures: Annotated[list[str], add]  # accumulated as Lv6+ sign

    # Output — on quorum
    onchain_tx_hash: str
    finalized: bool


def build_graph(
    checkpointer: BaseCheckpointSaver,
    llm_client=None,  # Claude Sonnet 4.6 (primary) or Murakumo Gemma (fallback)
    council_dispatcher=None,  # interface to Council Lv6+ notification
    charter_registry_port=None,  # interface to ChartersComplianceRegistry contract
):
    """Cell entrypoint.

    Two call-sites are supported (per ADR-2605202200 + ADR-2605232100):
      1. New contract: `cell_host.py` calls `build_graph(deps: CellDeps)` —
         see the module-level `__call__` adapter below which unwraps deps
         and re-invokes this function with the four positional kwargs.
      2. Legacy direct call: tests + ad-hoc invocations pass the four args
         explicitly. Defaults to None so the Pod can boot without all deps
         wired (substrate ports / council interface not yet exported by
         the production cell-host).

    Missing deps degrade gracefully — nodes that need them log + return
    state unchanged rather than crashing the runner subprocess.
    """
    g = StateGraph(CharterAttestationRequestState)

    g.add_node("load_request", load_request)
    g.add_node("validate_evidence", validate_evidence)
    g.add_node("llm_analyze", lambda s: llm_analyze(s, llm_client))
    g.add_node("dispatch_to_council", lambda s: dispatch_to_council(s, council_dispatcher))
    g.add_node("collect_signatures", collect_signatures)
    g.add_node("emit_onchain", lambda s: emit_onchain(s, charter_registry_port))
    g.add_node("emit_at_record", emit_at_record)

    g.add_edge(START, "load_request")
    g.add_edge("load_request", "validate_evidence")
    g.add_edge("validate_evidence", "llm_analyze")

    # Conditional: LLM recommendation drives next node
    def llm_router(state: CharterAttestationRequestState) -> str:
        rec = state.get("llm_recommendation")
        if rec == "forward_to_council":
            return "dispatch_to_council"
        elif rec == "reject_unfounded":
            return "emit_at_record"  # close with rejection record, no Council burden
        else:
            return "emit_at_record"  # request_more_evidence path; close with status record

    g.add_conditional_edges("llm_analyze", llm_router)
    g.add_edge("dispatch_to_council", "collect_signatures")

    # Conditional: ≥3 signatures → emit onchain, else loop back to collect
    def quorum_router(state: CharterAttestationRequestState) -> str:
        if len(state.get("council_signatures", [])) >= 3:
            return "emit_onchain"
        return "collect_signatures"  # await more signatures (checkpointer pauses here)

    g.add_conditional_edges("collect_signatures", quorum_router)
    g.add_edge("emit_onchain", "emit_at_record")
    g.add_edge("emit_at_record", END)

    return g.compile(checkpointer=checkpointer)


# ─── Node functions ──────────────────────────────────────────────────


def load_request(state: CharterAttestationRequestState) -> CharterAttestationRequestState:
    """Load the charter-attestation-request record from MST."""
    # TODO: fetch via @etzhayyim/sdk checkpointer sidecar (per ADR-2605171800)
    return state


def validate_evidence(state: CharterAttestationRequestState) -> CharterAttestationRequestState:
    """Validate evidence URIs are resolvable (IPFS / HTTP / AT URI)."""
    # TODO: check each evidence_uri is fetchable + content-hash matches if specified
    return state


def llm_analyze(state: CharterAttestationRequestState, llm_client) -> CharterAttestationRequestState:
    """LLM pre-analysis: does evidence support the alleged Rider violation?"""
    # TODO: load prompts/llm_analyze.txt + invoke llm_client with subject + evidence
    return {
        **state,
        "llm_summary": "...",
        "llm_rider_section_match_confidence": 0.0,
        "llm_recommendation": "forward_to_council",
        "llm_rationale": "...",
    }


def dispatch_to_council(state: CharterAttestationRequestState, council_dispatcher) -> CharterAttestationRequestState:
    """Notify Council Lv6+ members for deliberation."""
    # TODO: emit com.etzhayyim.apps.etzhayyim.charter-attestation-council-dispatch record
    return state


def collect_signatures(state: CharterAttestationRequestState) -> CharterAttestationRequestState:
    """Wait for Council Lv6+ signatures via MST listener.

    This node is a fixed-point — the graph pauses here (via checkpointer) until
    new signatures arrive. The MST listener triggers re-entry to this node
    with updated `council_signatures` accumulator.
    """
    return state


def emit_onchain(state: CharterAttestationRequestState, charter_registry_port) -> CharterAttestationRequestState:
    """Emit ChartersComplianceRegistry.attestNonAligned() tx on Base L2."""
    # TODO: call charter_registry_port.attest_non_aligned(...)
    return {**state, "onchain_tx_hash": "0x...", "finalized": True}


def emit_at_record(state: CharterAttestationRequestState) -> CharterAttestationRequestState:
    """Emit com.etzhayyim.apps.etzhayyim.charter-attestation record to MST."""
    # TODO: write via @etzhayyim/sdk checkpointer sidecar
    return state
