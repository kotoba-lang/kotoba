from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ConnectionState(TypedDict):
    part_id: str
    material: str
    dimensions: dict
    validation_score: float
    status: str

def validate_spec(state: ConnectionState) -> ConnectionState:
    # Simulate CAD and physical property validation
    if state.get('dimensions', {}).get('tolerance', 0.0) < 0.01:
        state['validation_score'] = 0.95
        state['status'] = 'VALIDATED'
    else:
        state['validation_score'] = 0.2
        state['status'] = 'REJECTED'
    return state

def assembly_routing(state: ConnectionState) -> str:
    return 'VALIDATED' if state['status'] == 'VALIDATED' else 'REJECTED'

graph = StateGraph(ConnectionState)
graph.add_node('validate', validate_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
