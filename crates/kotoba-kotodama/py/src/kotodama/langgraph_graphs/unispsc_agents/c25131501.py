from typing import TypedDict
from langgraph.graph import StateGraph, END

class AircraftState(TypedDict):
    serial_number: str
    compliance_checked: bool
    airworthiness_status: str

def validate_certification(state: AircraftState):
    print('Validating airworthiness certificate...')
    return {'compliance_checked': True}

def check_agricultural_specs(state: AircraftState):
    print('Checking spray system and payload specs...')
    return {'airworthiness_status': 'verified'}

graph = StateGraph(AircraftState)
graph.add_node('validate', validate_certification)
graph.add_node('specs', check_agricultural_specs)
graph.add_edge('validate', 'specs')
graph.add_edge('specs', END)
graph.set_entry_point('validate')
graph = graph.compile()
