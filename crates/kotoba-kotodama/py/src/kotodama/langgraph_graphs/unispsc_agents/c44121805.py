from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class CorrectionPenState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list[str]

def validate_specs(state: CorrectionPenState):
    specs = state.get('spec_data', {})
    errors = []
    if 'drying_time' not in specs: errors.append('Missing drying_time')
    if 'solvent_type' not in specs: errors.append('Missing solvent_type')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: CorrectionPenState):
    return 'process' if state['validation_passed'] else END

graph = StateGraph(CorrectionPenState)
graph.add_node('validate', validate_specs)
graph.add_node('process', lambda x: {'error_log': ['Proceeding to procurement']})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()
