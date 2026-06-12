from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class CoalProcessState(TypedDict):
    purity_check: bool
    moisture_level: float
    particle_distribution: List[float]
    approval_status: bool

def validate_purity(state: CoalProcessState):
    # Simulated Purity Logic
    is_pure = state.get('purity_check', False)
    return {'approval_status': is_pure}

def check_physical_constraints(state: CoalProcessState):
    # Simulate moisture and particle validation
    moisture = state.get('moisture_level', 10.0)
    return {'approval_status': moisture < 5.0}

graph = StateGraph(CoalProcessState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_physical', check_physical_constraints)
graph.add_edge('validate_purity', 'check_physical')
graph.add_edge('check_physical', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()
