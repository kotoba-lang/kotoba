from typing import TypedDict
from langgraph.graph import StateGraph, END

class EquipmentState(TypedDict):
    equipment_type: str
    specs_verified: bool
    compliance_check: bool

def validate_specs(state: EquipmentState):
    state['specs_verified'] = True
    return state

def run_compliance(state: EquipmentState):
    state['compliance_check'] = True
    return state

graph = StateGraph(EquipmentState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', run_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
