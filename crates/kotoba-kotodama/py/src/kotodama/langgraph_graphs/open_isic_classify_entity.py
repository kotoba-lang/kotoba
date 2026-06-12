"""
open_isic.classifyEntity — LangGraph StateGraph replacing classifyEntity.bpmn.

This graph routes classification requests to the correct industry-specific
MCP tool based on the ISIC code, and then emits the appropriate audit event.
"""

from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph


class OpenIsicClassifyState(TypedDict, total=False):
    vertexId: str
    isicClassCode: str
    entityDid: str
    entityName: str
    confidence: float
    classifiedAt: str
    callerDid: str

    # Outputs from classification
    verification: str
    requireReview: bool
    status: str
    classDid: str
    ok: bool
    error: str | None


def _get_mcp_nsid_for_code(code: str) -> str | None:
    if not code or len(code) != 4:
        return None
    return f"com.etzhayyim.apps.openIsic{code}.classify"


async def call_mcp_tool(state: OpenIsicClassifyState) -> dict:
    from kotodama.mcp_dispatch import build_default_handlers, handle_envelope

    code = state.get("isicClassCode", "")
    nsid = _get_mcp_nsid_for_code(code)
    if not nsid:
        return {"ok": False, "error": f"Could not determine MCP tool for ISIC code: {code}"}

    envelope = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": nsid,
            "arguments": {
                "vertexId": state.get("vertexId", ""),
                "isicClassCode": code,
                "entityDid": state.get("entityDid", ""),
                "entityName": state.get("entityName", ""),
                "confidence": state.get("confidence", 0.0),
                "classifiedAt": state.get("classifiedAt", ""),
                "callerDid": state.get("callerDid", ""),
            },
        },
    }

    handlers = build_default_handlers()
    status, body = await handle_envelope(envelope, handlers)

    if status != 200:
        return {"ok": False, "error": f"MCP error {status}: {body}"}

    result = body.get("result", {})
    if result.get("isError"):
        return {"ok": False, "error": str(result.get("content"))}

    # Extract JSON content from MCP result
    content = result.get("content", [])
    out = {}
    for item in content:
        if item.get("type") == "text":
            try:
                out.update(json.loads(item["text"]))
            except Exception:
                pass

    if not out.get("ok"):
        return {"ok": False, "error": out.get("error", "Unknown error in classification")}

    return {
        "ok": True,
        "vertexId": out.get("vertexId"),
        "verification": out.get("verification"),
        "requireReview": out.get("requireReview"),
        "status": out.get("status"),
        "classDid": out.get("classDid"),
    }


def route_review(state: OpenIsicClassifyState) -> str:
    if not state.get("ok"):
        return END
    if state.get("requireReview"):
        return "emit_audit_review"
    return "emit_audit_accept"


async def emit_audit_review(state: OpenIsicClassifyState) -> dict:
    from kotodama.primitives.active_inference import _emit_audit_internal

    _emit_audit_internal(
        actor="did:web:open-isic.etzhayyim.com",
        action="openIsic.classify.reviewPending",
        payload={
            "vertexId": state.get("vertexId"),
            "isicClassCode": state.get("isicClassCode"),
            "entityDid": state.get("entityDid"),
            "confidence": state.get("confidence"),
            "verification": state.get("verification"),
            "classifiedAt": state.get("classifiedAt"),
        },
    )
    return {}


async def emit_audit_accept(state: OpenIsicClassifyState) -> dict:
    from kotodama.primitives.active_inference import _emit_audit_internal

    _emit_audit_internal(
        actor="did:web:open-isic.etzhayyim.com",
        action="openIsic.classify.accept",
        payload={
            "vertexId": state.get("vertexId"),
            "isicClassCode": state.get("isicClassCode"),
            "entityDid": state.get("entityDid"),
            "verification": state.get("verification"),
            "classifiedAt": state.get("classifiedAt"),
        },
    )
    return {}


def build_graph():
    builder = StateGraph(OpenIsicClassifyState)
    builder.add_node("call_mcp_tool", call_mcp_tool)
    builder.add_node("emit_audit_review", emit_audit_review)
    builder.add_node("emit_audit_accept", emit_audit_accept)

    builder.set_entry_point("call_mcp_tool")
    builder.add_conditional_edges("call_mcp_tool", route_review)
    builder.add_edge("emit_audit_review", END)
    builder.add_edge("emit_audit_accept", END)

    return builder.compile()
