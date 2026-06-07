from typing import TypedDict
from langgraph.graph import StateGraph, END

class VentilatorState(TypedDict):
    device_id: str
    safety_check_passed: bool
    maintenance_records: dict
    approved: bool

def validate_safety(state: VentilatorState):
    # Simulate clinical safety protocol verification
    state['safety_check_passed'] = True
    return state

def check_compliance(state: VentilatorState):
    # Simulate regulatory compliance audit
    state['approved'] = state.get('safety_check_passed', False)
    return state

graph = StateGraph(VentilatorState)
graph.add_node('safety_check', validate_safety)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
