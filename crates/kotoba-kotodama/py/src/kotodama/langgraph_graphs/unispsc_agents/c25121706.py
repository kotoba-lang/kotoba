from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict

class DraftGearState(TypedDict):
    spec_data: Dict
    validation_status: str

def validate_specs(state: DraftGearState):
    specs = state.get('spec_data', {})
    if specs.get('load_capacity_kn', 0) > 0:
        return {'validation_status': 'COMPLIANT'}
    return {'validation_status': 'FAILED'}

def finalize_order(state: DraftGearState):
    return {'validation_status': 'READY_FOR_RFQ'}

graph = StateGraph(DraftGearState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
