from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_tin_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    required = ['alloy', 'tolerance']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

workflow = StateGraph(ProcurementState)
workflow.add_node('validate', validate_tin_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
