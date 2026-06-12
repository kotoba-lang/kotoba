from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    part_specs: dict
    validation_passed: bool
    compliance_risk: str

def validate_machining_specs(state: ProcessingState):
    specs = state.get('part_specs', {})
    is_valid = all(k in specs for k in ['material', 'tolerance'])
    return {'validation_passed': is_valid}

def check_export_controls(state: ProcessingState):
    return {'compliance_risk': 'high' if state.get('part_specs', {}).get('material') == 'titanium' else 'low'}

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_machining_specs)
graph.add_node('compliance', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
