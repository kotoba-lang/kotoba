from typing import TypedDict
from langgraph.graph import StateGraph, END

class GlassPipeState(TypedDict):
    specs: dict
    validation_passed: bool

def validate_glass_pipe(state: GlassPipeState):
    specs = state.get('specs', {})
    # Logic: Validate pressure rating against industry standards (e.g., Borosilicate)
    is_valid = specs.get('pressure_resistance_rating', 0) > 0 and 'glass_type' in specs
    return {'validation_passed': is_valid}

graph = StateGraph(GlassPipeState)
graph.add_node('validate', validate_glass_pipe)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
