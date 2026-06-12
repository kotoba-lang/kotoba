from typing import TypedDict
from langgraph.graph import StateGraph, END

class XRayComponentState(TypedDict):
    part_number: str
    compliance_docs: list
    radiation_shielding_verified: bool
    thermal_test_passed: bool

def validate_compliance(state: XRayComponentState):
    # Simulate regulatory validation logic
    state['compliance_docs'] = ['IEC_60601_Cert', 'FDA_510k']
    return state

def verify_safety_standards(state: XRayComponentState):
    # Simulate technical safety inspection
    state['radiation_shielding_verified'] = True
    state['thermal_test_passed'] = True
    return state

graph = StateGraph(XRayComponentState)
graph.add_node('compliance', validate_compliance)
graph.add_node('safety', verify_safety_standards)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
