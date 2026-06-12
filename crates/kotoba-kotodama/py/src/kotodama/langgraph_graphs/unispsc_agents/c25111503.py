from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShipProcurementState(TypedDict):
    imo_number: str
    compliance_verified: bool
    registry_check: bool

def validate_imo(state: ShipProcurementState):
    print(f'Validating IMO number: {state.get('imo_number')}')
    return {'compliance_verified': True}

def check_sanctions(state: ShipProcurementState):
    print('Performing sanctions screening on vessel registry...')
    return {'registry_check': True}

graph = StateGraph(ShipProcurementState)
graph.add_node('validate_imo', validate_imo)
graph.add_node('check_sanctions', check_sanctions)
graph.set_entry_point('validate_imo')
graph.add_edge('validate_imo', 'check_sanctions')
graph.add_edge('check_sanctions', END)
graph = graph.compile()
