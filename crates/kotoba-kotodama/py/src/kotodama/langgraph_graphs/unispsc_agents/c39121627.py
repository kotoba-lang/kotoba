from typing import TypedDict
from langgraph.graph import StateGraph, END

class FuseState(TypedDict):
    specifications: dict
    is_compliant: bool
    validation_log: list

def validate_fuse_specs(state: FuseState):
    specs = state.get("specifications", {})
    log = []
    compliant = True
    if not specs.get("interrupting_rating"):
        log.append("Missing Interrupting Rating")
        compliant = False
    return {"is_compliant": compliant, "validation_log": log}

graph = StateGraph(FuseState)
graph.add_node("validate_fuse", validate_fuse_specs)
graph.set_entry_point("validate_fuse")
graph.add_edge("validate_fuse", END)
graph = graph.compile()
