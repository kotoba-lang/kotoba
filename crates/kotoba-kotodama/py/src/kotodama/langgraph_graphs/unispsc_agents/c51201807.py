from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_id: str
    quality_docs: List[str]
    temperature_validated: bool

def validate_cold_chain(state: ProcurementState):
    return {"temperature_validated": True}

def check_compliance(state: ProcurementState):
    return {"quality_docs": ["Certificate of Analysis", "BSL-2 Validation"]}

graph = StateGraph(ProcurementState)
graph.add_node("cold_chain", validate_cold_chain)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("cold_chain")
graph.add_edge("cold_chain", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
