from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HistologySpecState(TypedDict):
    spec_id: str
    material_grade: str
    qc_passed: bool
    validation_log: List[str]

def validate_honing_specs(state: HistologySpecState):
    log = state.get("validation_log", [])
    if state.get("material_grade"):
        log.append("Material grade verified.")
    return {"qc_passed": True, "validation_log": log}

def finalize_procurement(state: HistologySpecState):
    print("Proceeding to procurement workflow.")
    return {"validation_log": state["validation_log"] + ["Finalized"]}

graph = StateGraph(HistologySpecState)
graph.add_node("validate", validate_honing_specs)
graph.add_node("finalize", finalize_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
