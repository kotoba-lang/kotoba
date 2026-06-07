from typing import TypedDict
from langgraph.graph import StateGraph, END

class TraceState(TypedDict):
    material_type: str
    is_non_toxic: bool
    age_group: str
    approved: bool

def validate_materials(state: TraceState):
    if state.get('is_non_toxic'):
        return {'approved': True}
    return {'approved': False}

def route_by_material(state: TraceState):
    return 'process_paper' if state['material_type'] == 'paper' else 'process_plastic'

graph = StateGraph(TraceState)
graph.add_node('validate', validate_materials)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
