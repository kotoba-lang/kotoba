from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChassisState(TypedDict):
    chassis_id: str
    spec_compliance: bool
    inspection_result: dict

def validate_specs(state: ChassisState):
    # Business logic for confirming chassis build specs
    return {"spec_compliance": True}

def perform_inspection(state: ChassisState):
    # Business logic for structural integrity inspection
    return {"inspection_result": {"status": "passed"}}

graph = StateGraph(ChassisState)
graph.add_node("validate", validate_specs)
graph.add_node("inspect", perform_inspection)
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph.set_entry_point("validate")
graph = graph.compile()
