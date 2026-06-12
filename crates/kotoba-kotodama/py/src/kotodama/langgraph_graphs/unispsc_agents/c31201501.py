from typing import TypedDict
from langgraph.graph import StateGraph, END

class TapeSpecState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_tape_specs(state: TapeSpecState):
    specs = state.get('spec_data', {})
    # Simple validation logic for adhesive strength
    is_valid = specs.get('adhesive_strength', 0) > 10
    return {'validation_result': is_valid}

graph = StateGraph(TapeSpecState)
graph.add_node('validate', validate_tape_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
