from typing import TypedDict
from langgraph.graph import StateGraph, END

class GasCylinderState(TypedDict):
    pressure_validated: bool
    safety_cert_verified: bool
    compliant: bool

def validate_pressure(state: GasCylinderState):
    state['pressure_validated'] = True
    return {'pressure_validated': True}

def verify_safety(state: GasCylinderState):
    state['safety_cert_verified'] = True
    return {'safety_cert_verified': True}

def finalize_check(state: GasCylinderState):
    state['compliant'] = state['pressure_validated'] and state['safety_cert_verified']
    return {'compliant': state['compliant']}

graph = StateGraph(GasCylinderState)
graph.add_node('validate_pressure', validate_pressure)
graph.add_node('verify_safety', verify_safety)
graph.add_node('finalize', finalize_check)
graph.add_edge('validate_pressure', 'verify_safety')
graph.add_edge('verify_safety', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate_pressure')

graph = graph.compile()
