from langgraph.graph import StateGraph, END
from typing import TypedDict

class ProcureState(TypedDict):
    item_id: str
    is_sterile: bool
    compliance_docs: list
    status: str

def validate_certification(state: ProcureState):
    return {"status": "VALIDATED" if state.get("is_sterile") else "REJECTED"}

def update_records(state: ProcureState):
    return {"status": "READY_FOR_PROCUREMENT"}

graph = StateGraph(ProcureState)
graph.add_node("validate", validate_certification)
graph.add_node("log", update_records)
graph.add_edge("validate", "log")
graph.add_edge("log", END)
graph.set_entry_point("validate")
graph = graph.compile()
