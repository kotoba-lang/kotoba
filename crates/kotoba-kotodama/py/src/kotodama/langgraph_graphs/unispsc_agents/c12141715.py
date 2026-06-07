from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    spec_id: str
    viscosity_check: bool
    thermal_validation: bool
    is_approved: bool

def validate_viscosity(state: LubricantState) -> LubricantState:
    # Simulate technical validation
    state['viscosity_check'] = True
    return state

def validate_thermal(state: LubricantState) -> LubricantState:
    # Simulate safety inspection
    state['thermal_validation'] = True
    return state

def approve_procurement(state: LubricantState) -> LubricantState:
    state['is_approved'] = state['viscosity_check'] and state['thermal_validation']
    return state

graph = StateGraph(LubricantState)
graph.add_node('viscosity', validate_viscosity)
graph.add_node('thermal', validate_thermal)
graph.add_node('approval', approve_procurement)
graph.add_edge('viscosity', 'thermal')
graph.add_edge('thermal', 'approval')
graph.add_edge('approval', END)
graph.set_entry_point('viscosity')
graph = graph.compile()
