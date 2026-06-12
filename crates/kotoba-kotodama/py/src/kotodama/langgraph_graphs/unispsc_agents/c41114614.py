from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MetalTestingState(TypedDict):
    instrument_type: str
    calibration_status: bool
    compliance_checks: List[str]
    approved: bool

def validate_instrument(state: MetalTestingState):
    checks = []
    if state.get('calibration_status'):
        checks.append('Calibration verified')
    return {'compliance_checks': checks, 'approved': len(checks) > 0}

graph = StateGraph(MetalTestingState)
graph.add_node('validate', validate_instrument)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
