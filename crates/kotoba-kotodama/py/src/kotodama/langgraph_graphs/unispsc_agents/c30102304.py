from typing import TypedDict
from langgraph.graph import StateGraph, END

class SteelSpecState(TypedDict):
    material_grade: str
    dimensions: dict
    mill_certificate: bool
    approved: bool

def validate_materials(state: SteelSpecState):
    # Simulate validation logic for steel profile specs
    valid = state.get('mill_certificate', False) and state.get('material_grade') in ['SS400', 'SM490']
    return {'approved': valid}

graph_builder = StateGraph(SteelSpecState)
graph_builder.add_node('validate', validate_materials)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', END)
graph = graph_builder.compile()
