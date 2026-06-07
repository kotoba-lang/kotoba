from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FlooringSpecState(TypedDict):
    material_type: str
    spec_sheet_url: str
    compliance_result: bool
    validation_errors: List[str]

def validate_flooring_specs(state: FlooringSpecState):
    errors = []
    if not state.get('material_type'):
        errors.append('Missing material type')
    return {'validation_errors': errors, 'compliance_result': len(errors) == 0}

graph = StateGraph(FlooringSpecState)
graph.add_node('validate', validate_flooring_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
