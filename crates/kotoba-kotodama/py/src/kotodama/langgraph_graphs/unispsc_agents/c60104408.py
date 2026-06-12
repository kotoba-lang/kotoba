from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GeologyKitState(TypedDict):
    kit_id: str
    specimens: List[str]
    validation_errors: List[str]
    is_approved: bool

def validate_contents(state: GeologyKitState):
    # Simulate validation logic for geology kit components
    errors = []
    if not state.get('specimens'):
        errors.append('Missing specimen list')
    return {'validation_errors': errors, 'is_approved': len(errors) == 0}

graph = StateGraph(GeologyKitState)
graph.add_node('validate', validate_contents)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
