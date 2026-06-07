from typing import TypedDict
from langgraph.graph import StateGraph, END

class TruckState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_truck_specs(state: TruckState):
    specs = state.get('spec_data', {})
    valid = specs.get('payload_capacity_kg', 0) > 0 and 'emission_standard' in specs
    return {'validation_result': valid}

graph = StateGraph(TruckState)
graph.add_node('validator', validate_truck_specs)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
