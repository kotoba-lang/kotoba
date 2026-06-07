"""
ossekai_aggregate_publisher — Aggregate Publisher cell.
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

class PublisherState(TypedDict, total=False):
    context: dict
    wellbecoming_advisory: dict
    feed_post_attestation: dict

def _ingest_advisory(state: PublisherState) -> dict:
    ctx = state.get("context", {}) or {}
    return {"wellbecoming_advisory": ctx.get("wellbecoming_advisory", {})}

def _publish_feed_post(state: PublisherState) -> dict:
    """Publish anonymized public-good intel summaries to AT Protocol."""
    advisory = state.get("wellbecoming_advisory", {})
    if not advisory:
        return {"feed_post_attestation": {}}
        
    return {
        "feed_post_attestation": {
            "status": "published",
            "channel": "app.bsky.feed.post",
            "content": advisory.get("content", "")
        }
    }

_g = StateGraph(PublisherState)
_g.add_node("ingest_advisory", _ingest_advisory)
_g.add_node("publish_feed_post", _publish_feed_post)
_g.add_edge(START, "ingest_advisory")
_g.add_edge("ingest_advisory", "publish_feed_post")
_g.add_edge("publish_feed_post", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

if wit_world:
    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, compiled)
