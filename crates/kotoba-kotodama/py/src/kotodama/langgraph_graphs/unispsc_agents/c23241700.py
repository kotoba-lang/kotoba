from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DeburringState(TypedDict):
    machine_id: str
    specifications: dict
    is_compliant: bool
    safety_check_passed: bool

def validate_specs(state: DeburringState) -> DeburringState:
    specs = state.get('specifications', {})
    state['is_compliant'] = all(k in specs for k in ['power', 'material_limit'])
    return state

def safety_verification(state: DeburringState) -> DeburringState:
    if state.get('is_compliant'):
        state['safety_check_passed'] = True
    return state

graph = StateGraph(DeburringState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_verification)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()
