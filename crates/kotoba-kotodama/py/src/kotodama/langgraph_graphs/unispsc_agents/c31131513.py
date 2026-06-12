from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    specifications: dict
    validation_errors: List[str]
    approved: bool

def validate_specs(state: ForgingState):
    specs = state.get('specifications', {})
    errors = []
    if 'alloy_grade' not in specs: errors.append('Missing alloy grade')
    if specs.get('tensile_strength', 0) < 150: errors.append('Tensile strength below threshold')
    return {'validation_errors': errors, 'approved': len(errors) == 0}

def process_forging(state: ForgingState):
    return state

graph = StateGraph(ForgingState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_forging)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
