from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ChemicalProcessState(TypedDict):
    material_id: str
    purity_check: bool
    safety_audit_passed: bool
    log: Annotated[List[str], operator.add]

def validate_material(state: ChemicalProcessState):
    # Simulate chemical validation logic
    return {"purity_check": True, "log": ["Material validation completed."]}

def conduct_safety_audit(state: ChemicalProcessState):
    # Simulate safety and export control audit
    return {"safety_audit_passed": True, "log": ["Safety and export audit passed."]}

graph = StateGraph(ChemicalProcessState)
graph.add_node("validate", validate_material)
graph.add_node("audit", conduct_safety_audit)
graph.add_edge("validate", "audit")
graph.add_edge("audit", END)
graph.set_entry_point("validate")
graph = graph.compile()
