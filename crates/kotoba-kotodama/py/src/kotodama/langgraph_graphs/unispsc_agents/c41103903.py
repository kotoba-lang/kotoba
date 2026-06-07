from typing import TypedDict
from langgraph.graph import StateGraph, END

class CentrifugeState(TypedDict):
    spec_data: dict
    validation_status: str

def validate_specs(state: CentrifugeState):
    specs = state.get('spec_data', {})
    if specs.get('max_rpm', 0) > 0 and 'iso_cert' in specs:
        return {'validation_status': 'COMPLIANT'}
    return {'validation_status': 'NON_COMPLIANT'}

graph = StateGraph(CentrifugeState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
