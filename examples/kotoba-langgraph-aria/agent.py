"""kotoba-langgraph-aria — ARIA actor as a kotoba WASM LangGraph component.

Flagship port of kotodama's ARIA actor onto the WASM-native ``kotoba_langgraph``
API so it compiles to a kotoba-node component (`componentize-py`) and runs
in-WASM on a live kotoba server (`:8077`) via invoke.run / kotoba_wasm_run.

This module is the *build entrypoint*: ``scripts/build-pywasm.sh`` runs
``componentize-py componentize agent`` against the module basename, so the file
MUST be named ``agent.py`` and MUST expose the ``WitWorld.run`` export.

Graph (faithful to upstream ARIA):
    START → ingest_all → compute_area → minimax_select → narrate → witness → END

Signals (6, projected from the invocation context):
    emotion · attention · request · market · money · influence

vs. the original `aria_kotoba.py` this adds one node — ``narrate`` — which routes
the minimax decision through ``KotobaLLM`` (kotoba:kais/llm WIT import). On a live
host the host binds that import to the Murakumo fleet; the deployed inference
model is **gemma-4-26B-A4B** (MoE) via LiteLLM 127.0.0.1:4000 per ADR-2605302355
/ Charter "Murakumo-only inference" invariant (ADR-2605215000). Leave
``model_cid=""`` so the host's ``MURAKUMO_DEFAULT_MODEL`` selects gemma-4-26B-A4B.

Build:
    ./scripts/build-pywasm.sh examples/kotoba-langgraph-aria/agent.py
Deploy (in-WASM on the running :8077 node — see README.md for the exact call):
    kotoba_wasm_run / invoke.run with the produced agent.wasm
"""

from __future__ import annotations

from typing import Any, TypedDict

import wit_world

from kotoba_langgraph import (
    StateGraph,
    KotobaLLM,
    KotobaCheckpointer,
    START,
    END,
    handle_invoke,
)

# componentize-py static analysis does not follow the lazy
# `from kotoba_langgraph._cbor import loads` inside _entry.handle_invoke, nor the
# lazy `from wit_world.imports import llm` inside kotoba_langgraph.llm._wit_infer.
# Pull all three to module scope so they are bundled into the component
# (otherwise it traps at call time with ModuleNotFoundError). Mirrors agent.py /
# aria_kotoba.py in kotoba-langgraph-hello (ADR-2605301625/2605302355 follow-up).
import kotoba_langgraph._cbor  # noqa: F401
import kotoba_langgraph._entry  # noqa: F401
import wit_world.imports.llm  # noqa: F401


# ── State ──────────────────────────────────────────────────────────────────

class AriaState(TypedDict, total=False):
    context: dict
    threadId: str
    budgetMs: int
    emotion: dict
    attention: dict
    request: dict
    market: dict
    money: dict
    influence: dict
    area_integral: float
    eta_global: float
    minimax_result: dict
    narrative: str
    narrate_error: str
    witnessed: bool
    audit_cid: str


_SIGNAL_KEYS = ("emotion", "attention", "request", "market", "money", "influence")


# ── LLM (routed through kotoba:kais/llm WIT → Murakumo gemma-4-26B-A4B) ──────

# model_cid="" → host MURAKUMO_DEFAULT_MODEL (gemma-4-26B-A4B). Charter requires
# all religious-corp inference go through the Murakumo fleet; the WASM component
# never embeds a model or a network client — it only emits the llm.infer import.
_llm = KotobaLLM(
    model_cid="",
    system_prompt=(
        "You are ARIA, a terse situational-awareness narrator. Given a chosen "
        "action and a hedge over six signals, state in one sentence what to do "
        "and why. No preamble."
    ),
)


# ── Nodes (decision logic identical to upstream aria.py) ────────────────────

def _ingest_all(state: AriaState) -> dict:
    """Project the six signals out of the invocation context."""
    ctx = state.get("context", {}) or {}
    return {k: ctx.get(k, {}) for k in _SIGNAL_KEYS}


def _compute_area(state: AriaState) -> dict:
    """Information-area integral + global decay (eta) — upstream logic."""
    signals = [state.get(k, {}) for k in _SIGNAL_KEYS]
    area = 0.0
    for s in signals:
        v = s.get("intensity", 0.0) if isinstance(s, dict) else 0.0
        area += float(v)
    eta = area / (len(signals) or 1)
    return {"area_integral": area, "eta_global": eta}


def _minimax_select(state: AriaState) -> dict:
    """Von Neumann minimax over the signal payoff vector — upstream logic."""
    signals = {k: state.get(k, {}) for k in _SIGNAL_KEYS}
    scored = {
        k: float(v.get("intensity", 0.0)) if isinstance(v, dict) else 0.0
        for k, v in signals.items()
    }
    best = max(scored, key=scored.get) if scored else None
    worst = min(scored, key=scored.get) if scored else None
    return {"minimax_result": {"action": best, "hedge": worst, "scores": scored}}


def _narrate(state: AriaState) -> dict:
    """Route the minimax decision through gemma-4-26B-A4B for a one-line rationale.

    The LLM is advisory only — it narrates the already-decided minimax result;
    it does NOT change the action/hedge (witness records the deterministic
    decision, not the prose).
    """
    mr = state.get("minimax_result", {}) or {}
    prompt = [{
        "role": "user",
        "content": (
            f"action={mr.get('action')} hedge={mr.get('hedge')} "
            f"scores={mr.get('scores')}"
        ),
    }]
    # The LLM narration is advisory. If host inference is unavailable (e.g. the
    # Murakumo gateway returns an error), the deterministic minimax decision must
    # still flow through to `witness` — so swallow inference failures and emit an
    # empty narrative rather than aborting the whole graph.
    try:
        msg = _llm.invoke(prompt)
        narrative = msg.get("content", "")
    except Exception as e:  # noqa: BLE001 — narration must never break the actor
        narrative = ""
        return {"narrative": narrative, "narrate_error": str(e)[:200]}
    return {"narrative": narrative}


def _witness(state: AriaState) -> dict:
    """Witness attestation — emit audit record over the deterministic decision."""
    mr = state.get("minimax_result", {})
    return {"witnessed": True, "audit_cid": "aria:" + str(mr.get("action", "none"))}


# ── Graph ───────────────────────────────────────────────────────────────────

_g = StateGraph(AriaState)
_g.add_node("ingest_all", _ingest_all)
_g.add_node("compute_area", _compute_area)
_g.add_node("minimax_select", _minimax_select)
_g.add_node("narrate", _narrate)
_g.add_node("witness", _witness)
_g.add_edge(START, "ingest_all")
_g.add_edge("ingest_all", "compute_area")
_g.add_edge("compute_area", "minimax_select")
_g.add_edge("minimax_select", "narrate")
_g.add_edge("narrate", "witness")
_g.add_edge("witness", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())


# ── kotoba-node WIT export (boilerplate, always the same) ────────────────────

class WitWorld(wit_world.WitWorld):
    def run(self, ctx_cbor: bytes) -> bytes:
        return handle_invoke(ctx_cbor, compiled)
