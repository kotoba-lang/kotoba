from typing import TypedDict
from langgraph.graph import StateGraph, END

class PosterState(TypedDict):
    material_type: str
    dimensions: str
    is_verified: bool

def validate_specs(state: PosterState):
    state['is_verified'] = True if state.get('material_type') else False
    return state

def assembly_process(state: PosterState):
    print('Initiating production workflow for DIY poster component')
    return state

graph = StateGraph(PosterState)
graph.add_node('validate', validate_specs)
graph.add_node('assemble', assembly_process)
graph.set_entry_point('validate')
graph.add_edge('validate', 'assemble')
graph.add_edge('assemble', END)
graph = graph.compile()
