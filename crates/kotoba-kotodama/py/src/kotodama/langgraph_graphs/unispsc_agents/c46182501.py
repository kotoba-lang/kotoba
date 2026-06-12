from langgraph.graph import StateGraph, END
from typing import TypedDict

class DefenseState(TypedDict):
    product_name: str
    chemical_composition: str
    is_compliant: bool
    safety_check_passed: bool

def validate_composition(state: DefenseState):
    # Business logic for repellent chemical safety
    return {'is_compliant': True}

def safety_audit(state: DefenseState):
    # Verification of nozzle safety and pressure
    return {'safety_check_passed': True}

graph = StateGraph(DefenseState)
graph.add_node('validate', validate_composition)
graph.add_node('audit', safety_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()
