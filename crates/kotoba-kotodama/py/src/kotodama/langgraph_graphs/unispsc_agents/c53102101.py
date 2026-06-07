from typing import TypedDict
from langgraph.graph import StateGraph, END

class ClothingState(TypedDict):
    spec_data: dict
    compliance_passed: bool

def validate_textile_specs(state: ClothingState) -> ClothingState:
    # Logic to verify fabric flame retardancy and chemical toxicity limits
    specs = state.get('spec_data', {})
    is_compliant = 'flame_retardant' in specs and 'toxin_free' in specs
    return {'compliance_passed': is_compliant}

def update_registry(state: ClothingState) -> ClothingState:
    if state.get('compliance_passed'):
        print('Logging compliant textile procurement.')
    return state

graph = StateGraph(ClothingState)
graph.add_node('validate', validate_textile_specs)
graph.add_node('record', update_registry)
graph.set_entry_point('validate')
graph.add_edge('validate', 'record')
graph.add_edge('record', END)
graph = graph.compile()
