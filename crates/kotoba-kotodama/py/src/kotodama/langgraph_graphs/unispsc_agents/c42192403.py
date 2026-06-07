from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class IsolationCartState(TypedDict):
    cart_id: str
    spec_compliance: bool
    inspection_report: str
    approval_status: str

def validate_specs(state: IsolationCartState):
    # Simulate CAD and material compliance check
    print(f'Validating specs for {state[cart_id]}')
    return {'spec_compliance': True}

def approval_step(state: IsolationCartState):
    return {'approval_status': 'APPROVED' if state['spec_compliance'] else 'REJECTED'}

graph = StateGraph(IsolationCartState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_step)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
