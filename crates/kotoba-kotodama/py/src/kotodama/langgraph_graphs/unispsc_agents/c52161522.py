from typing import TypedDict
from langgraph.graph import StateGraph, END

class ScannerState(TypedDict):
    device_id: str
    frequency_compliance: bool
    encryption_verified: bool

def validate_frequency(state: ScannerState):
    # Simulate RF frequency validation logic
    state['frequency_compliance'] = True
    return state

def check_security(state: ScannerState):
    # Simulate encryption protocol validation
    state['encryption_verified'] = True
    return state

graph = StateGraph(ScannerState)
graph.add_node('validate_rf', validate_frequency)
graph.add_node('verify_security', check_security)
graph.set_entry_point('validate_rf')
graph.add_edge('validate_rf', 'verify_security')
graph.add_edge('verify_security', END)
graph = graph.compile()
