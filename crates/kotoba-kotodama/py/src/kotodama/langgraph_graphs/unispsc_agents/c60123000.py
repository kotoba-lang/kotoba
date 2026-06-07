from typing import TypedDict
from langgraph.graph import StateGraph, END

class CraftState(TypedDict):
    material_type: str
    dimensions: dict
    approved: bool

def validate_foam(state: CraftState):
    # Business logic for foam density/safety classification
    state['approved'] = state.get('material_type') == 'EPS' or state.get('material_type') == 'XPS'
    return state

def check_compliance(state: CraftState):
    # Compliance check for standard craft supplies
    print(f'Validating specs: {state}')
    return {'approved': state['approved']}

graph = StateGraph(CraftState)
graph.add_node('validate', validate_foam)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)

graph = graph.compile()
