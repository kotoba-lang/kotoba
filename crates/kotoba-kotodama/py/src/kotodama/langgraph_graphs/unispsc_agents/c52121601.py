from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    spec_compliance: bool
    approval_status: str

def validate_towels(state: ProcurementState):
    # Simulate spec verification logic
    state['spec_compliance'] = True
    return {'spec_compliance': True, 'approval_status': 'Validated'}

def update_status(state: ProcurementState):
    return {'approval_status': 'Ready for Procurement'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_towels)
graph.add_node('finalize', update_status)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
