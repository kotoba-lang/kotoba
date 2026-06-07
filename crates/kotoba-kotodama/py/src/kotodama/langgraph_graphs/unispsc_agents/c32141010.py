from typing import TypedDict
from langgraph.graph import StateGraph, END

class PMTState(TypedDict):
    spec_data: dict
    validated: bool

def validate_specs(state: PMTState):
    required = ['spectral_range', 'quantum_efficiency', 'dark_current']
    state['validated'] = all(k in state.get('spec_data', {}) for k in required)
    return state

def compliance_check(state: PMTState):
    print('Running dual-use export control screening...')
    return state

graph = StateGraph(PMTState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', compliance_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
