from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    spec_completed: bool
    validation_errors: List[str]

def validate_specs(state: ProcurementState):
    errors = []
    if not state.get('spec_completed'):
        errors.append('Missing mandatory biological safety certifications.')
    return {'validation_errors': errors}

def route_procurement(state: ProcurementState):
    if state['validation_errors']:
        return 'error_handler'
    return 'approve_procurement'

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('error_handler', lambda x: x)
graph.add_node('approve_procurement', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_procurement)
graph.add_edge('error_handler', END)
graph.add_edge('approve_procurement', END)
graph = graph.compile()
