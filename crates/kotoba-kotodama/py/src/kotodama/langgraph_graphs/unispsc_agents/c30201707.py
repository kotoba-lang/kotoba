from typing import TypedDict
from langgraph.graph import StateGraph, END

class WarehouseState(TypedDict):
    facility_id: str
    compliance_passed: bool
    details: dict

def validate_zoning(state: WarehouseState):
    print(f'Validating zoning for {state.get('facility_id')}')
    return {'compliance_passed': True}

def finalize_procurement(state: WarehouseState):
    print('Procurement finalized')
    return {'compliance_passed': True}

graph = StateGraph(WarehouseState)
graph.add_node('validate_zoning', validate_zoning)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate_zoning')
graph.add_edge('validate_zoning', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
