from typing import TypedDict
from langgraph.graph import StateGraph, END

class RazorWireState(TypedDict):
    spec_data: dict
    is_compliant: bool
    alert_flag: bool

def validate_safety_specs(state: RazorWireState):
    specs = state.get('spec_data', {})
    # Check for mandatory safety certifications
    compliant = 'safety_cert' in specs and specs['tensile_strength'] > 1200
    return {'is_compliant': compliant, 'alert_flag': not compliant}

workflow = StateGraph(RazorWireState)
workflow.add_node('validation', validate_safety_specs)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
