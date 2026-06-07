from typing import TypedDict
from langgraph.graph import StateGraph, END

class AircraftState(TypedDict):
    serial_number: str
    compliance_cleared: bool
    export_approved: bool

def validate_specs(state: AircraftState) -> AircraftState:
    if not state.get('serial_number'):
        raise ValueError('Missing serial number')
    state['compliance_cleared'] = True
    return state

def check_export(state: AircraftState) -> AircraftState:
    state['export_approved'] = True
    return state

graph = StateGraph(AircraftState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
