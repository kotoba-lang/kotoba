from typing import TypedDict
from langgraph.graph import StateGraph, END

class UVAssemblyState(TypedDict):
    specs: dict
    validated: bool
    error: str

def validate_specs(state: UVAssemblyState):
    s = state.get('specs', {})
    is_valid = all(k in s for k in ['UV_transmission', 'tensile_strength'])
    return {'validated': is_valid}

def process_assembly(state: UVAssemblyState):
    return {'error': None if state['validated'] else 'Invalid Specs'}

graph = StateGraph(UVAssemblyState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_assembly)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
