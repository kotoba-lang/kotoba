from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    animal_id: str
    health_status: str
    inspection_logs: Annotated[Sequence[str], operator.add]
    is_cleared: bool

def validate_health(state: LivestockState) -> LivestockState:
    # Logic to verify health certificate via external registry
    if state.get('health_status') == 'certified':
        state['is_cleared'] = True
    return state

def process_logistics(state: LivestockState) -> LivestockState:
    # Logic to plan transport and compliance check
    state['inspection_logs'] = ['Logistics Plan Approved']
    return state

graph = StateGraph(LivestockState)
graph.add_node('validate', validate_health)
graph.add_node('logistics', process_logistics)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('validate')
graph = graph.compile()
