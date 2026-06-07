"""kotoba-langgraph-echo — minimal LangGraph actor compiled to a kotoba WASM component.

Faithful port of kotodama's `echo` actor
(`40-engine/kotoba/crates/kotoba-kotodama/py/src/kotodama/langgraph_graphs/echo.py`) onto the
WASM-native `kotoba_langgraph` API. Smallest possible graph — returns the input
`prompt` verbatim — used as a deterministic liveness probe for the
actor-as-kotoba-WASM pattern.

Build entrypoint must be named `agent.py` (componentize target = module basename)
and expose the `WitWorld.run` export.

Build:
    ./scripts/build-pywasm.sh examples/kotoba-langgraph-echo/agent.py
Run (in-WASM on :8077): MCP `kotoba_wasm_run` — see ../kotoba-langgraph-aria/README.md
for the verified recipe (unique agent_did + ctx encoded with kotoba_langgraph._cbor).
"""

from __future__ import annotations

from typing import TypedDict

import wit_world

from kotoba_langgraph import StateGraph, KotobaCheckpointer, START, END, handle_invoke

# Force-bundle the lazily-imported submodules so componentize-py includes them.
import kotoba_langgraph._cbor  # noqa: F401
import kotoba_langgraph._entry  # noqa: F401


class EchoState(TypedDict, total=False):
    prompt: str
    response: str


def _echo(state: EchoState) -> dict:
    return {"response": state.get("prompt", "")}


_g = StateGraph(EchoState)
_g.add_node("echo", _echo)
_g.add_edge(START, "echo")
_g.add_edge("echo", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())


class WitWorld(wit_world.WitWorld):
    def run(self, ctx_cbor: bytes) -> bytes:
        return handle_invoke(ctx_cbor, compiled)
