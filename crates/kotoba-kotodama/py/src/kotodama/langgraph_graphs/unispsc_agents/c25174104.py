from typing import TypedDict
from langgraph.graph import StateGraph, END

class RoofTopState(TypedDict):
    vehicle_model: str
    material_spec: str
    is_compliant: bool

def validate_roof_specs(state: RoofTopState):
    compliant = state.get('material_spec') in ['Canvas', 'Vinyl'] and state.get('vehicle_model') != ''
    return {'is_compliant': compliant}

graph = StateGraph(RoofTopState)
graph.add_node('validate', validate_roof_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
