from typing import TypedDict
from langgraph.graph import StateGraph, END

class GutterState(TypedDict):
    material: str
    flow_capacity: float
    status: str

def validate_specs(state: GutterState):
    if state.get('flow_capacity', 0) < 0:
        return {'status': 'rejected'}
    return {'status': 'approved'}

def route_verification(state: GutterState):
    return 'validate'

graph = StateGraph(GutterState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
