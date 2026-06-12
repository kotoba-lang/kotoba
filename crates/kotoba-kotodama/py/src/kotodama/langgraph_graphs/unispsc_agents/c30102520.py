from typing import TypedDict
from langgraph.graph import StateGraph, END

class NickelSheetState(TypedDict):
    spec_data: dict
    validation_result: bool
    compliance_report: str

def validate_nickel_spec(state: NickelSheetState):
    spec = state.get('spec_data', {})
    is_valid = spec.get('purity', 0) >= 99.0 and 'ASTM' in spec.get('standard', '')
    return {'validation_result': is_valid, 'compliance_report': 'Passed' if is_valid else 'Failed: Impurity or standard mismatch'}

def route_by_validation(state: NickelSheetState):
    return 'validate' if not state.get('validation_result') else END

graph = StateGraph(NickelSheetState)
graph.add_node('validate', validate_nickel_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
