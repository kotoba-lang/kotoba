import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_content: str
    validation_errors: Annotated[list, operator.add]
    is_approved: bool

def validate_content(state: ProcurementState):
    # Simulate validation of educational content against standards
    errors = []
    if not state.get('spec_content'):
        errors.append('Missing content specification')
    return {'validation_errors': errors}

def approve_procurement(state: ProcurementState):
    return {'is_approved': len(state['validation_errors']) == 0}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_content)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
