from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class AnimalState(TypedDict):
    animal_id: str
    health_status: str
    quarantine_verified: bool

def validate_health(state: AnimalState):
    return {'health_status': 'verified' if state.get('health_status') == 'healthy' else 'rejected'}

def check_quarantine(state: AnimalState):
    return {'quarantine_verified': True}

graph = StateGraph(AnimalState)
graph.add_node('validate', validate_health)
graph.add_node('quarantine', check_quarantine)
graph.set_entry_point('validate')
graph.add_edge('validate', 'quarantine')
graph.add_edge('quarantine', END)
graph = graph.compile()
