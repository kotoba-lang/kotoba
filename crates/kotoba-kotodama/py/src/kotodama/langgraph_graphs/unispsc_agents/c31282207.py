from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    specs: dict
    validation_results: Annotated[list, operator.add]
    status: str

def validate_materials(state: ProcurementState):
    # Simulate material compliance check
    return {"validation_results": ["Material grade compliant"], "status": "validating_dimensions"}

def validate_dimensions(state: ProcurementState):
    # Simulate tolerance check
    return {"validation_results": ["Dimensional tolerances within range"], "status": "complete"}

graph = StateGraph(ProcurementState)
graph.add_node("material_check", validate_materials)
graph.add_node("dim_check", validate_dimensions)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "dim_check")
graph.add_edge("dim_check", END)
graph = graph.compile()
