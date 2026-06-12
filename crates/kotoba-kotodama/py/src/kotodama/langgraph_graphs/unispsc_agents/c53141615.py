from langgraph.graph import StateGraph, END
from typing import TypedDict

class ProcessingState(TypedDict):
    needle_specs: dict
    validation_passed: bool

def validate_needle_specs(state: ProcessingState):
    specs = state.get('needle_specs', {})
    is_valid = all(key in specs for key in ['gauge', 'material'])
    print(f'Validating specs: {is_valid}')
    return {'validation_passed': is_valid}

workflow = StateGraph(ProcessingState)
workflow.add_node('validate', validate_needle_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
