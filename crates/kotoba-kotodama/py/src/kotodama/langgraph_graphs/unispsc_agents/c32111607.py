from langgraph.graph import StateGraph, END
from typing import TypedDict

class TransistorState(TypedDict):
    part_number: str
    spec_check_passed: bool
    compliance_status: str

def validate_specs(state: TransistorState):
    # Simulate checking RF performance metrics
    state['spec_check_passed'] = True
    return {'spec_check_passed': True}

def verify_compliance(state: TransistorState):
    # Simulate dual-use/export check
    state['compliance_status'] = 'CLEARED'
    return {'compliance_status': 'CLEARED'}

graph = StateGraph(TransistorState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
