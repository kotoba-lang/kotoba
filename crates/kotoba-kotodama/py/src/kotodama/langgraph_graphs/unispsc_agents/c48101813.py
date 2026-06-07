from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    material: str
    compliance_check: bool
    approved: bool

def validate_material(state: KitchenwareState):
    state['compliance_check'] = state.get('material') == 'SUS304'
    return state

def approval_step(state: KitchenwareState):
    state['approved'] = state['compliance_check']
    return state

graph = StateGraph(KitchenwareState)
graph.add_node('validate', validate_material)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)

# Compile the graph
graph = graph.compile()
