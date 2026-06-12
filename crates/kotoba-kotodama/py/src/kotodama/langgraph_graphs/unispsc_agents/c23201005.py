from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class VehicleState(TypedDict):
    vehicle_id: str
    specifications: dict
    is_compliant: bool

def validate_specs(state: VehicleState):
    specs = state.get('specifications', {})
    # Business logic for industrial grade vehicle validation
    compliant = 'engine_type' in specs and 'safety_rating' in specs
    return {'is_compliant': compliant}

graph = StateGraph(VehicleState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
