from typing import TypedDict
from langgraph.graph import StateGraph, END

class PoolEquipState(TypedDict):
    equipment_type: str
    spec_verified: bool
    compliance_check: bool

def validate_specs(state: PoolEquipState):
    state['spec_verified'] = True
    return state

def check_compliance(state: PoolEquipState):
    state['compliance_check'] = True
    return state

graph = StateGraph(PoolEquipState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
