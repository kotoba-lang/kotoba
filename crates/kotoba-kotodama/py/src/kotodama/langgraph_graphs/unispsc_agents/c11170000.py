from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    material_id: str
    purity_validation: bool
    safety_check: bool
    logistics_ready: bool

def validate_material(state: ChemicalProcurementState):
    # Simulate chemical property verification logic
    return {"purity_validation": True}

def safety_audit(state: ChemicalProcurementState):
    # Simulate regulatory/compliance audit
    return {"safety_check": True}

def logistics_routing(state: ChemicalProcurementState):
    # Simulate supply chain and dangerous goods handling
    return {"logistics_ready": True}

graph = StateGraph(ChemicalProcurementState)
graph.add_node("validate", validate_material)
graph.add_node("audit", safety_audit)
graph.add_node("logistics", logistics_routing)
graph.set_entry_point("validate")
graph.add_edge("validate", "audit")
graph.add_edge("audit", "logistics")
graph.add_edge("logistics", END)
graph = graph.compile()
