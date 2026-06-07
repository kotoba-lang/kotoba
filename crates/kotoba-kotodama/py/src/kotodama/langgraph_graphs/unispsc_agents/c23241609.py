from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingGraphState(TypedDict):
    weld_head_id: str
    spec_check: bool
    compliance_ok: bool

def validate_specs(state: WeldingGraphState):
    # Simulate CAD/Spec validation for robotics gear
    state['spec_check'] = True
    return state

def check_compliance(state: WeldingGraphState):
    # Simulate regulatory/dual-use export check
    state['compliance_ok'] = True
    return state

graph = StateGraph(WeldingGraphState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
