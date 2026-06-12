from typing import TypedDict
from langgraph.graph import StateGraph, END

class AutomationState(TypedDict):
    equipment_id: str
    spec_verified: bool
    compliance_check: bool

def validate_specs(state: AutomationState):
    state['spec_verified'] = True
    return state

def check_compliance(state: AutomationState):
    state['compliance_check'] = True
    return state

graph = StateGraph(AutomationState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
