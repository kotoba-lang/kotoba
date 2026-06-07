from typing import TypedDict
from langgraph.graph import StateGraph, END

class BowlingSupplyState(TypedDict):
    item_name: str
    spec_check: bool
    approved: bool

def validate_specs(state: BowlingSupplyState):
    # Simulate CAD/technical specification validation for bowling equipment
    state['spec_check'] = True if 'weight' in str(state) else False
    return {'spec_check': state['spec_check']}

def approval_node(state: BowlingSupplyState):
    state['approved'] = state['spec_check']
    return {'approved': state['approved']}

graph = StateGraph(BowlingSupplyState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_node)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
