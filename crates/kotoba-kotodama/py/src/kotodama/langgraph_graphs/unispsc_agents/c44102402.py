from typing import TypedDict
from langgraph.graph import StateGraph, END

class OfficeMachineryState(TypedDict):
    device_id: str
    spec_compliance: bool
    validation_report: str

def validate_machinery_spec(state: OfficeMachineryState):
    # Simulate CAD or mechanical spec validation logic
    state['spec_compliance'] = True
    state['validation_report'] = 'High-precision stamping mechanism verified.'
    return state

workflow = StateGraph(OfficeMachineryState)
workflow.add_node('validate', validate_machinery_spec)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
