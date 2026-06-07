"""
EthicsContentClassifierCell — Pregel cell for Eros / Gore boundary classification.

Per ADR-2605192400 (Eros / Gore Council Judging Framework).

3-layer framework:
  Layer 1: LLM pre-classification (T1-T5)
  Layer 2: Council Lv6+ deliberation (T2/T4 borderline only)
  Layer 3: Precedent Registry application

Trigger: synchronous HTTP API (port 13114)
Effect: returns classification + (if needed) initiates Council deliberation

Murakumo node: benjamin (leader), asher (failover replica)
"""

from __future__ import annotations

from typing import Literal, TypedDict, Annotated
from operator import add

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver


Tier = Literal["T1", "T2", "T3", "T4", "T5"]
Determination = Literal["permit", "prohibit", "conditional", "council_required"]


class EthicsContentClassifierState(TypedDict, total=False):
    # Input
    content_uri: str
    content_metadata: dict
    requesting_app_did: str
    deployment_context: str  # "internal" / "external" / "religious-art" / "documentary" / etc.

    # Layer 3: precedent search
    applicable_precedents: list[str]  # at:// URIs of matching past precedents
    precedent_determination: Determination | None

    # Layer 1: LLM classification (skipped if precedent matches)
    llm_tier: Tier
    llm_rationale: str
    llm_factors: dict  # {"eros_factors": {...}, "gore_factors": {...}}

    # Layer 2: Council dispatch (only if T2 / T4 and no precedent)
    council_required: bool
    council_dispatch_uri: str | None
    council_signatures: Annotated[list[str], add]
    council_determination: Determination | None

    # Output
    final_determination: Determination
    final_rationale: str
    new_precedent_uri: str | None  # set if Council ruling established a new precedent


def build_graph(
    checkpointer: BaseCheckpointSaver,
    llm_client_primary,  # Claude Sonnet 4.6
    llm_client_fallback,  # Murakumo Gemma 3:4b (for sensitive content not sent to Anthropic)
    precedent_registry,  # interface to com.etzhayyim.apps.etzhayyim.eros-gore-precedent collection
    council_dispatcher,
):
    g = StateGraph(EthicsContentClassifierState)

    g.add_node("load_content", load_content)
    g.add_node("search_precedents", lambda s: search_precedents(s, precedent_registry))
    g.add_node("llm_classify", lambda s: llm_classify(s, llm_client_primary, llm_client_fallback))
    g.add_node("apply_precedent", apply_precedent)
    g.add_node("dispatch_to_council", lambda s: dispatch_to_council(s, council_dispatcher))
    g.add_node("collect_signatures", collect_signatures)
    g.add_node("record_precedent", lambda s: record_precedent(s, precedent_registry))
    g.add_node("synthesize", synthesize)
    g.add_node("emit_record", emit_record)

    g.add_edge(START, "load_content")
    g.add_edge("load_content", "search_precedents")

    # Conditional: if precedent matches, skip LLM
    def precedent_router(state: EthicsContentClassifierState) -> str:
        if state.get("applicable_precedents") and state.get("precedent_determination"):
            return "apply_precedent"
        return "llm_classify"

    g.add_conditional_edges("search_precedents", precedent_router)
    g.add_edge("apply_precedent", "synthesize")

    # Conditional: T2/T4 → Council, others → synthesize directly
    def tier_router(state: EthicsContentClassifierState) -> str:
        tier = state.get("llm_tier")
        if tier in ("T2", "T4"):
            return "dispatch_to_council"
        return "synthesize"  # T1 permit / T3 permit / T5 prohibit

    g.add_conditional_edges("llm_classify", tier_router)
    g.add_edge("dispatch_to_council", "collect_signatures")

    # Conditional: ≥3 signatures → record precedent + synthesize
    def quorum_router(state: EthicsContentClassifierState) -> str:
        if len(state.get("council_signatures", [])) >= 3:
            return "record_precedent"
        return "collect_signatures"  # await more signatures

    g.add_conditional_edges("collect_signatures", quorum_router)
    g.add_edge("record_precedent", "synthesize")
    g.add_edge("synthesize", "emit_record")
    g.add_edge("emit_record", END)

    return g.compile(checkpointer=checkpointer)


# ─── Node functions ──────────────────────────────────────────────────


def load_content(state: EthicsContentClassifierState) -> EthicsContentClassifierState:
    """Load content metadata from URI."""
    return state


def search_precedents(state: EthicsContentClassifierState, precedent_registry) -> EthicsContentClassifierState:
    """Vector search precedent registry for similar past determinations."""
    # TODO: lancedb-wasm based vector search over precedent corpus
    return state


def llm_classify(
    state: EthicsContentClassifierState,
    llm_primary,
    llm_fallback,
) -> EthicsContentClassifierState:
    """5-tier classification rubric (Eros T1, Eros Borderline T2, Neutral T3, Gore Borderline T4, Gore T5).

    Sensitive content (per ADR-2605181100 encrypted records) bypasses external LLM and uses local fallback.
    """
    is_sensitive = state.get("content_metadata", {}).get("encrypted", False)
    llm = llm_fallback if is_sensitive else llm_primary
    # TODO: invoke llm with prompts/rubric.txt + content
    return {
        **state,
        "llm_tier": "T3",  # placeholder
        "llm_rationale": "...",
        "llm_factors": {},
    }


def apply_precedent(state: EthicsContentClassifierState) -> EthicsContentClassifierState:
    """Apply precedent determination directly (Council deferral bypassed)."""
    return {
        **state,
        "final_determination": state["precedent_determination"],
        "final_rationale": f"applied precedent {state['applicable_precedents'][0]}",
    }


def dispatch_to_council(
    state: EthicsContentClassifierState,
    council_dispatcher,
) -> EthicsContentClassifierState:
    """Send T2/T4 borderline case to Council Lv6+ for deliberation."""
    return state


def collect_signatures(state: EthicsContentClassifierState) -> EthicsContentClassifierState:
    """Fixed-point — wait for Council signatures."""
    return state


def record_precedent(
    state: EthicsContentClassifierState,
    precedent_registry,
) -> EthicsContentClassifierState:
    """Record the Council ruling as a new precedent."""
    return state


def synthesize(state: EthicsContentClassifierState) -> EthicsContentClassifierState:
    """Combine LLM / precedent / Council outputs into final determination."""
    if not state.get("final_determination"):
        tier = state.get("llm_tier")
        if tier == "T1" or tier == "T3":
            return {**state, "final_determination": "permit", "final_rationale": state.get("llm_rationale", "")}
        if tier == "T5":
            return {**state, "final_determination": "prohibit", "final_rationale": state.get("llm_rationale", "")}
        if state.get("council_determination"):
            return {
                **state,
                "final_determination": state["council_determination"],
                "final_rationale": "council deliberation",
            }
    return state


def emit_record(state: EthicsContentClassifierState) -> EthicsContentClassifierState:
    """Emit com.etzhayyim.apps.etzhayyim.eros-gore-judging record to MST."""
    return state
