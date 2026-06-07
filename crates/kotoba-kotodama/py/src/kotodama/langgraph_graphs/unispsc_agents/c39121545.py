from typing import TypedDict
from langgraph.graph import StateGraph, END

class EStopState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_safety_standards(state: EStopState):
    compliance = state.get('spec_data', {}).get('ISO_13850', False)
    return {'validation_results': ['ISO 13850 check passed' if compliance else 'ISO 13850 check failed'], 'is_compliant': compliance}

def finalize_procurement(state: EStopState):
    return {'is_compliant': state['is_compliant']}

graph = StateGraph(EStopState)
graph.add_node('validate', validate_safety_standards)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
