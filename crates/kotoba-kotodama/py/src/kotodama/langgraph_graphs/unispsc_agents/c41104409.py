from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class IncubatorState(TypedDict):
    spec_sheet: dict
    validation_passed: bool
    compliance_tags: List[str]

def validate_specs(state: IncubatorState):
    specs = state.get('spec_sheet', {})
    valid = specs.get('temp_precision', 0) <= 0.1
    return {'validation_passed': valid}

def route_compliance(state: IncubatorState):
    return 'process_order' if state['validation_passed'] else 'flag_review'

graph = StateGraph(IncubatorState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
