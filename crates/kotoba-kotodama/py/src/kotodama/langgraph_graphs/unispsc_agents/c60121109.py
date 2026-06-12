from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    is_validated: bool

def validate_paper_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    # Check for mandatory technical specs for watercolor paper
    required = ['basis_weight_gsm', 'acid_free_certification']
    is_valid = all(k in specs for k in required)
    return {'is_validated': is_valid}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_paper_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
