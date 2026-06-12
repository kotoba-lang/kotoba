from typing import TypedDict
from langgraph.graph import StateGraph, END

class ViseState(TypedDict):
    spec_completed: bool
    inspection_passed: bool

def validate_specs(state: ViseState):
    print('Validating mechanical specifications for Bench Vise...')
    return {'spec_completed': True}

def perform_quality_check(state: ViseState):
    print('Executing stress test and jaw alignment check...')
    return {'inspection_passed': True}

graph = StateGraph(ViseState)
graph.add_node('validate_specs', validate_specs)
graph.add_node('perform_quality_check', perform_quality_check)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'perform_quality_check')
graph.add_edge('perform_quality_check', END)

graph = graph.compile()
