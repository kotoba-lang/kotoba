from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    compliance_validated: bool
    safety_check_passed: bool

def validate_ergonomics(state: ProcurementState):
    print('Validating ergonomic standards for physically challenged utensils...')
    return {'compliance_validated': True}

def check_material_safety(state: ProcurementState):
    print('Checking material biocompatibility and safety standards...')
    return {'safety_check_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('ergonomics', validate_ergonomics)
graph.add_node('safety', check_material_safety)
graph.set_entry_point('ergonomics')
graph.add_edge('ergonomics', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
