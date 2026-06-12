from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ExteriorState(TypedDict):
    material_type: str
    specifications: dict
    is_compliant: bool

def validate_materials(state: ExteriorState):
    specs = state.get('specifications', {})
    # Check for basic fire compliance
    compliant = specs.get('fire_rating', 0) >= 1
    return {'is_compliant': compliant}

graph = StateGraph(ExteriorState)
graph.add_node('validate', validate_materials)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
