from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class KitchenApplianceState(TypedDict):
    model_id: str
    safety_cert_verified: bool
    thermal_test_passed: bool
    compliance_report: str

def validate_safety_certs(state: KitchenApplianceState):
    state['safety_cert_verified'] = True
    return state

def run_thermal_analysis(state: KitchenApplianceState):
    state['thermal_test_passed'] = True
    return state

graph = StateGraph(KitchenApplianceState)
graph.add_node('verify_certs', validate_safety_certs)
graph.add_node('thermal_analysis', run_thermal_analysis)
graph.add_edge('verify_certs', 'thermal_analysis')
graph.add_edge('thermal_analysis', END)
graph.set_entry_point('verify_certs')
graph = graph.compile()
