from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CopyPaperState(TypedDict):
    paper_id: str
    spec: dict
    validation_log: List[str]
    is_approved: bool

def validate_paper_specs(state: CopyPaperState):
    log = state.get("validation_log", [])
    spec = state.get("spec", {})
    if spec.get("brightness", 0) >= 90:
        log.append("Brightness validated.")
    else:
        log.append("Brightness below standard.")
    return {"validation_log": log}

def quality_control_node(state: CopyPaperState):
    is_approved = len(state["validation_log"]) > 0
    return {"is_approved": is_approved}

graph = StateGraph(CopyPaperState)
graph.add_node("validate", validate_paper_specs)
graph.add_node("qc", quality_control_node)
graph.set_entry_point("validate")
graph.add_edge("validate", "qc")
graph.add_edge("qc", END)
graph = graph.compile()
