from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    spec_data: dict
    validation_results: dict

def validate_cad(state: ExtrusionState):
    # Simulate CAD validation logic
    state['validation_results'] = {'cad_pass': True}
    return state

def check_metallurgy(state: ExtrusionState):
    # Simulate metallurgical compliance check
    return {'validation_results': {**state.get('validation_results', {}), 'metallurgy_ok': True}}

graph = StateGraph(ExtrusionState)
graph.add_node('cad_validation', validate_cad)
graph.add_node('metallurgy_check', check_metallurgy)
graph.set_entry_point('cad_validation')
graph.add_edge('cad_validation', 'metallurgy_check')
graph.add_edge('metallurgy_check', END)
graph = graph.compile()
