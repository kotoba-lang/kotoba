from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    specifications: dict
    validation_errors: List[str]
    is_compliant: bool

def validate_specs(state: ProcurementState):
    specs = state.get('specifications', {})
    errors = []
    if specs.get('leak_proof_test_standard') != 'ISO-standard':
        errors.append('Invalid leak-proof standard')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
