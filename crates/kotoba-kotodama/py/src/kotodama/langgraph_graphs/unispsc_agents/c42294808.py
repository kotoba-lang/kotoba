from typing import TypedDict
from langgraph.graph import StateGraph, END

class EsophagoscopeState(TypedDict):
    device_id: str
    compliance_checked: bool
    sterility_verified: bool

def validate_specs(state: EsophagoscopeState):
    # Simulate regulatory validation logic
    state['compliance_checked'] = True
    return state

def check_sterility(state: EsophagoscopeState):
    # Simulate sterilization verification
    state['sterility_verified'] = True
    return state

workflow = StateGraph(EsophagoscopeState)
workflow.add_node('validate', validate_specs)
workflow.add_node('sterility', check_sterility)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'sterility')
workflow.add_edge('sterility', END)
graph = workflow.compile()
