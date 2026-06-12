from langgraph.graph import StateGraph, END
from typing import TypedDict

class CleaningToolState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_holder_specs(state: CleaningToolState):
    specs = state.get('spec_data', {})
    required = ['material', 'size', 'locking_type']
    is_compliant = all(key in specs for key in required)
    return {'is_compliant': is_compliant}

workflow = StateGraph(CleaningToolState)
workflow.add_node('validate', validate_holder_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
