from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AbsorbentMatState(TypedDict):
    material: str
    absorbency_l: float
    is_fire_retardant: bool
    validation_errors: List[str]

def validate_specs(state: AbsorbentMatState):
    errors = []
    if state.get('absorbency_l', 0) < 1.0:
        errors.append('Absorbency capacity too low for industrial grade')
    return {'validation_errors': errors}

def approval_node(state: AbsorbentMatState):
    return {'validation_errors': ['Pending Final Inspection'] if not state['validation_errors'] else state['validation_errors']}

graph = StateGraph(AbsorbentMatState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
