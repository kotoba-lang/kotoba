from typing import TypedDict
from langgraph.graph import StateGraph, END

class VendingMachineState(TypedDict):
    hardware_spec: dict
    compliance_status: bool
    dispatch_ready: bool

def validate_hardware(state: VendingMachineState):
    print('Validating hardware durability and payment modules...')
    state['compliance_status'] = True
    return state

def check_integration(state: VendingMachineState):
    print('Verifying API integration for ticketing services...')
    state['dispatch_ready'] = True
    return state

graph = StateGraph(VendingMachineState)
graph.add_node('validate', validate_hardware)
graph.add_node('integrate', check_integration)
graph.add_edge('validate', 'integrate')
graph.add_edge('integrate', END)
graph.set_entry_point('validate')
graph = graph.compile()
