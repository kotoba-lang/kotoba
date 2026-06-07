from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class AlloyState(TypedDict):
    material_code: str
    purity_cert_url: str
    analysis_results: List[dict]
    status: str

def validate_purity(state: AlloyState):
    # Simulate purity verification
    return {"status": "verified" if state.get("purity_cert_url") else "failed"}

def process_metallurgy(state: AlloyState):
    # Simulate metallurgical check
    return {"analysis_results": [{"check": "microstructure", "value": "pass"}]}

graph = StateGraph(AlloyState)
graph.add_node("validate", validate_purity)
graph.add_node("process", process_metallurgy)
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph.set_entry_point("validate")
graph = graph.compile()
