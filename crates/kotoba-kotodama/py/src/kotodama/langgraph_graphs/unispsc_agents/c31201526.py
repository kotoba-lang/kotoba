from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TapeProcurementState(TypedDict):
    capacity: float
    format: str
    is_validated: bool
    errors: List[str]

def validate_tape_spec(state: TapeProcurementState):
    errors = []
    if state.get('capacity', 0) <= 0:
        errors.append('Invalid storage capacity')
    return {'is_validated': len(errors) == 0, 'errors': errors}

graph = StateGraph(TapeProcurementState)
graph.add_node('validate', validate_tape_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
