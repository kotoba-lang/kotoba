from typing import TypedDict
from langgraph.graph import StateGraph, END

class PostOfficeState(TypedDict):
    service_type: str
    compliance_verified: bool
    sla_score: float

def validate_service(state: PostOfficeState):
    state['compliance_verified'] = True
    return state

def check_sla(state: PostOfficeState):
    state['sla_score'] = 1.0
    return state

graph = StateGraph(PostOfficeState)
graph.add_node('validate', validate_service)
graph.add_node('sla', check_sla)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sla')
graph.add_edge('sla', END)
graph = graph.compile()
