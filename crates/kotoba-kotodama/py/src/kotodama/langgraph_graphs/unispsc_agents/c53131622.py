from typing import TypedDict
from langgraph.graph import StateGraph, END

class CondomState(TypedDict):
    iso_compliant: bool
    inspection_passed: bool

def check_certification(state: CondomState):
    return {"iso_compliant": True}

def perform_quality_check(state: CondomState):
    return {"inspection_passed": True}

graph = StateGraph(CondomState)
graph.add_node("cert", check_certification)
graph.add_node("qc", perform_quality_check)
graph.set_entry_point("cert")
graph.add_edge("cert", "qc")
graph.add_edge("qc", END)
graph = graph.compile()
