from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HangerState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    is_compliant: bool

def validate_specs(state: HangerState):
    data = state.get('spec_data', {})
    errors = []
    if data.get('load_kg', 0) < 50:
        errors.append('Load capacity below minimum safety threshold')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

graph = StateGraph(HangerState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
