from typing import TypedDict
from langgraph.graph import StateGraph, END

class AircraftState(TypedDict):
    serial_number: str
    compliance_cleared: bool
    avionics_verified: bool

def validate_specs(state: AircraftState):
    print(f'Validating specs for {state[serial_number]}')
    return {'compliance_cleared': True}

def verify_avionics(state: AircraftState):
    print('Running avionics diagnostic suite...')
    return {'avionics_verified': True}

graph = StateGraph(AircraftState)
graph.add_node('validate', validate_specs)
graph.add_node('avionics', verify_avionics)
graph.set_entry_point('validate')
graph.add_edge('validate', 'avionics')
graph.add_edge('avionics', END)
graph = graph.compile()
