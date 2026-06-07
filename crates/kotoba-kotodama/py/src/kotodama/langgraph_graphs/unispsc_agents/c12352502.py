from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class WaferState(TypedDict):
    purity_check: bool
    inspection_report: str
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: WaferState) -> WaferState:
    # Simulate high-purity chemical analysis
    return {"purity_check": True, "validation_logs": ["Purity level 99.99999% verified"]}

def perform_inspection(state: WaferState) -> WaferState:
    return {"inspection_report": "Surface defects: None. Class: Prime Wafer.", "validation_logs": ["Inspection completed"]}

graph = StateGraph(WaferState)
graph.add_node("validate", validate_purity)
graph.add_node("inspect", perform_inspection)
graph.set_entry_point("validate")
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph = graph.compile()
