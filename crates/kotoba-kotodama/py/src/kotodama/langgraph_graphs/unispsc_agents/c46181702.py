from typing import TypedDict
from langgraph.graph import StateGraph, END

class FaceShieldState(TypedDict):
    spec_data: dict
    validated: bool
    compliance_report: str

def validate_compliance(state: FaceShieldState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['material', 'standard'])
    return {'validated': is_valid, 'compliance_report': 'Validated' if is_valid else 'Missing specs'}

def finalize_order(state: FaceShieldState):
    return {'compliance_report': 'Order ready for procurement'}

graph = StateGraph(FaceShieldState)
graph.add_node('validate', validate_compliance)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.set_entry_point('validate')
graph.add_edge('finalize', END)
graph = graph.compile()
