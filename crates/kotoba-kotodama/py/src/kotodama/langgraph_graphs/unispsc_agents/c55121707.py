from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SignState(TypedDict):
    dimensions: str
    magnet_strength: float
    is_validated: bool
    errors: List[str]

def validate_specs(state: SignState):
    errors = []
    if not state.get('dimensions'):
        errors.append('Dimensions missing')
    if state.get('magnet_strength', 0) < 0.5:
        errors.append('Magnet too weak for vehicle use')
    return {'is_validated': len(errors) == 0, 'errors': errors}

graph = StateGraph(SignState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
