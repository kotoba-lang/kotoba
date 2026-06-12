from typing import TypedDict
from langgraph.graph import StateGraph, END

class RollingPinState(TypedDict):
    spec_checked: bool
    compliance_passed: bool

def validate_material(state: RollingPinState):
    state['spec_checked'] = True
    return {'spec_checked': True}

def check_compliance(state: RollingPinState):
    state['compliance_passed'] = True
    return {'compliance_passed': True}

graph = StateGraph(RollingPinState)
graph.add_node('material_check', validate_material)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
