from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AnimalProcurementState(TypedDict):
    animal_id: str
    health_status: str
    transport_log: Annotated[Sequence[str], operator.add]
    is_cleared: bool

def validate_health_node(state: AnimalProcurementState):
    # Simulate health check logic
    status = 'CLEARED' if state.get('health_status') == 'HEALTHY' else 'FLAGGED'
    return {'is_cleared': status == 'CLEARED'}

def transport_node(state: AnimalProcurementState):
    return {'transport_log': ['Transport initiated', 'Temperature verified']}

graph = StateGraph(AnimalProcurementState)
graph.add_node('health_check', validate_health_node)
graph.add_node('transport', transport_node)
graph.add_edge('health_check', 'transport')
graph.add_edge('transport', END)
graph.set_entry_point('health_check')
graph = graph.compile()
