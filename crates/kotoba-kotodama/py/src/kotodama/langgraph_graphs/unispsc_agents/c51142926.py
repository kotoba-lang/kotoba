from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    license_valid: bool
    quantity: float
    compliance_cleared: bool

def check_regulatory_compliance(state: ProcurementState):
    # Simulate strict DEA/Regulatory check
    state['compliance_cleared'] = state.get('license_valid', False) and state.get('quantity', 0) < 500
    return state

def logistics_workflow(state: ProcurementState):
    if state['compliance_cleared']:
        print('Dispatching via secure regulated courier')
    else:
        print('Alert: Legal compliance violation')
    return state

graph = StateGraph(ProcurementState)
graph.add_node('compliance', check_regulatory_compliance)
graph.add_node('logistics', logistics_workflow)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()
