"""
open_isic_hierarchical_classify — Pregel StateGraph for hierarchical classification.

This graph takes an entity description and navigates down the ISIC Rev.4 tree
(Section -> Division -> Group -> Class) by iteratively fetching the taxonomy
options via the MCP tool `com.etzhayyim.apps.openIsic.getTaxonomy` and using the LLM
to make decisions at each layer.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class HierarchicalClassifyState(TypedDict, total=False):
    vertexId: str
    entityDid: str
    entityName: str
    description: str
    callerDid: str
    
    # Internal progression state
    currentLevel: str    # 'section' | 'division' | 'group' | 'class'
    currentCode: str     # '' | 'A' | '10' | '101'
    candidates: list[dict]
    
    # Outputs
    isicClassCode: str
    confidence: float
    classifiedAt: str
    ok: bool
    error: str | None


async def fetch_taxonomy(state: HierarchicalClassifyState) -> dict:
    from kotodama.mcp_dispatch import build_default_handlers, handle_envelope
    
    level = state.get("currentLevel", "section")
    parent_code = state.get("currentCode", "")
    
    envelope = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": "com.etzhayyim.apps.openIsic.getTaxonomy",
            "arguments": {
                "level": level,
                "parentCode": parent_code
            }
        }
    }
    
    handlers = build_default_handlers()
    status, body = await handle_envelope(envelope, handlers)
    
    if status != 200:
        return {"ok": False, "error": f"MCP getTaxonomy error {status}: {body}"}
        
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
        return {"ok": False, "error": out.get("error", "Unknown error in taxonomy fetch")}
        
    return {"candidates": out.get("items", []), "ok": True}


async def predict_level(state: HierarchicalClassifyState) -> dict:
    # Here we would normally call the LLM to select from `state['candidates']`
    # based on `state['entityName']` and `state['description']`.
    # For now, we simulate an LLM call by picking the first candidate (or a placeholder)
    # to demonstrate the graph structure.
    # In a real environment, this node dispatches an MCP call to `com.etzhayyim.tools.llm.chat`.
    
    level = state.get("currentLevel", "section")
    candidates = state.get("candidates", [])
    if not candidates:
        return {"ok": False, "error": f"No candidates found for {level}"}
        
    # Simulation of LLM selection
    selected = candidates[0]
    new_code = selected["code"]
    
    if level == "section":
        return {"currentLevel": "division", "currentCode": new_code, "ok": True}
    elif level == "division":
        return {"currentLevel": "group", "currentCode": new_code, "ok": True}
    elif level == "group":
        return {"currentLevel": "class", "currentCode": new_code, "ok": True}
    elif level == "class":
        return {
            "currentLevel": "done",
            "isicClassCode": new_code,
            "confidence": 0.95,
            "ok": True
        }
    
    return {"ok": False, "error": "Invalid level progression"}


def route_next(state: HierarchicalClassifyState) -> str:
    if not state.get("ok"):
        return END
    level = state.get("currentLevel")
    if level == "done":
        return "save_classification"
    return "fetch_taxonomy"


async def save_classification(state: HierarchicalClassifyState) -> dict:
    # After predicting the final class, we delegate to the unified MCP dispatcher
    # which routes to `openIsicC.classifyManufacturing` or similar.
    from kotodama.langgraph_graphs.open_isic_classify_entity import call_mcp_tool
    
    class_state = {
        "vertexId": state.get("vertexId", ""),
        "isicClassCode": state.get("isicClassCode", ""),
        "entityDid": state.get("entityDid", ""),
        "entityName": state.get("entityName", ""),
        "confidence": state.get("confidence", 0.9),
        "classifiedAt": state.get("classifiedAt", "2026-05-14T00:00:00Z"),
        "callerDid": state.get("callerDid", "")
    }
    
    # We await the flat classifier which triggers the final MCP tool
    result = await call_mcp_tool(class_state)
    return result


def build_graph():
    builder = StateGraph(HierarchicalClassifyState)
    builder.add_node("fetch_taxonomy", fetch_taxonomy)
    builder.add_node("predict_level", predict_level)
    builder.add_node("save_classification", save_classification)
    
    builder.set_entry_point("fetch_taxonomy")
    builder.add_edge("fetch_taxonomy", "predict_level")
    builder.add_conditional_edges("predict_level", route_next)
    builder.add_edge("save_classification", END)
    
    return builder.compile()
