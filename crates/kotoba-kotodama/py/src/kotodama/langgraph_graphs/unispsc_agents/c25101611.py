from typing import TypedDict
from langgraph.graph import StateGraph, END

class TruckState(TypedDict):
    vin: str
    compliance_checked: bool
    approval_status: str

def validate_truck_specs(state: TruckState) -> TruckState:
    print(f'Validating specs for VIN: {state.get('vin')}')
    return {'compliance_checked': True}

def update_approval(state: TruckState) -> TruckState:
    return {'approval_status': 'APPROVED'}

graph = StateGraph(TruckState)
graph.add_node('validate', validate_truck_specs)
graph.add_node('approve', update_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
