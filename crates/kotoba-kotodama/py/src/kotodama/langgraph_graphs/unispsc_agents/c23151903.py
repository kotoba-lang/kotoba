from typing import TypedDict
from langgraph.graph import StateGraph, END

class MotionControlState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_specs(state: MotionControlState):
    specs = state.get('spec_data', {})
    results = []
    if 'safety_rating' not in specs: results.append('Missing SIL/PL rating')
    if 'protocol' not in specs: results.append('No communication protocol defined')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def route_by_compliance(state: MotionControlState):
    return 'compliant' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(MotionControlState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
