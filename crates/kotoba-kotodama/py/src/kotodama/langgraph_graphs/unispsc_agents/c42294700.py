from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PerfusionState(TypedDict):
    device_id: str
    validation_checks: List[str]
    compliance_ok: bool

def validate_specs(state: PerfusionState):
    # Simulate critical clinical spec validation
    state['validation_checks'] = ['ISO_13485_VERIFIED', 'STERILITY_CHECKED']
    state['compliance_ok'] = True
    return state

def workflow_check(state: PerfusionState):
    return 'VALID' if state['compliance_ok'] else 'REJECT'

graph = StateGraph(PerfusionState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
