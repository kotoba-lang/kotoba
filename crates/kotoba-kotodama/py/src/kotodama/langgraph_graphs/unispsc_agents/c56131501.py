from typing import TypedDict
from langgraph.graph import StateGraph, END

class DisplayFormState(TypedDict):
    material: str
    dimensions: dict
    is_approved: bool

def validate_specs(state: DisplayFormState):
    # Business logic for mannequin dimension validation
    if state.get('dimensions', {}).get('bust', 0) > 0:
        return {'is_approved': True}
    return {'is_approved': False}

graph = StateGraph(DisplayFormState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
