from typing import TypedDict
from langgraph.graph import StateGraph, END

class HoseState(TypedDict):
    material: str
    pressure_rating: int
    is_compliant: bool

def validate_specs(state: HoseState):
    is_compliant = state.get('pressure_rating', 0) > 0 and len(state.get('material', '')) > 0
    return {'is_compliant': is_compliant}

def route_by_compliance(state: HoseState):
    return 'valid' if state['is_compliant'] else 'invalid'

graph = StateGraph(HoseState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
