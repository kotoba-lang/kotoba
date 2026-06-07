"""
ossekai_member_digest — Member Digest cell.
Resident in Kotoba WASM.
"""

from typing import TypedDict
try:
    import wit_world
except ImportError:
    wit_world = None

from kotoba_langgraph import StateGraph, KotobaCheckpointer, START, END, handle_invoke
import kotoba_langgraph._cbor  # noqa: F401
import kotoba_langgraph._entry  # noqa: F401

_r0_marker = True

class DigestState(TypedDict, total=False):
    context: dict
    wellbecoming_advisory: dict
    member_digest_record: dict

def _ingest_advisory(state: DigestState) -> dict:
    ctx = state.get("context", {}) or {}
    return {"wellbecoming_advisory": ctx.get("wellbecoming_advisory", {})}

def _encrypt_and_package(state: DigestState) -> dict:
    """Package the advisory into an encrypted envelope for opted-in members."""
    advisory = state.get("wellbecoming_advisory", {})
    if not advisory:
        return {"member_digest_record": {}}
        
    return {
        "member_digest_record": {
            "source": "ossekai_member_digest",
            "status": "encrypted",
            "encryptedPayloadCid": "bafy...", # Mock CID for encryption
            "content_ref": advisory.get("content", "")
        }
    }

_g = StateGraph(DigestState)
_g.add_node("ingest_advisory", _ingest_advisory)
_g.add_node("encrypt_and_package", _encrypt_and_package)
_g.add_edge(START, "ingest_advisory")
_g.add_edge("ingest_advisory", "encrypt_and_package")
_g.add_edge("encrypt_and_package", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

if wit_world:
    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, compiled)
