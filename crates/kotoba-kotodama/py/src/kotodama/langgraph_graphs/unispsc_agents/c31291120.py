from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    material_data: dict
    dimensions: dict
    approved: bool

def validate_dimensional_specs(state: ExtrusionState):
    # Perform precision validation logic
    tolerance = state.get('dimensions', {}).get('tolerance', 0.0)
    return {'approved': tolerance < 0.05}

def check_compliance(state: ExtrusionState):
    # Check dual-use export regulations
    return {'approved': state['approved'] and True}

graph = StateGraph(ExtrusionState)
graph.add_node('validate', validate_dimensional_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
