from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SealingState(TypedDict):
    spec_id: str
    material_certified: bool
    pressure_validated: bool
    approval_status: str

def validate_material(state: SealingState) -> SealingState:
    # Simulate material spec validation logic
    state['material_certified'] = True
    return state

def validate_pressure(state: SealingState) -> SealingState:
    # Simulate pressure tolerance calculation
    state['pressure_validated'] = True
    return state

def finalize_procurement(state: SealingState) -> SealingState:
    if state['material_certified'] and state['pressure_validated']:
        state['approval_status'] = 'APPROVED'
    else:
        state['approval_status'] = 'REJECTED'
    return state

graph = StateGraph(SealingState)
graph.add_node('material_check', validate_material)
graph.add_node('pressure_check', validate_pressure)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'pressure_check')
graph.add_edge('pressure_check', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
