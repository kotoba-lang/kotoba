from typing import TypedDict
from langgraph.graph import StateGraph, END

class DispenserState(TypedDict):
    device_id: str
    calibration_status: bool
    compliance_docs: list
    is_approved: bool

def validate_specs(state: DispenserState):
    # Simulate validation logic for drug dispenser compliance
    docs = state.get('compliance_docs', [])
    valid = 'ISO_13485' in docs and state.get('calibration_status', False)
    return {'is_approved': valid}

def route_verification(state: DispenserState):
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(DispenserState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
