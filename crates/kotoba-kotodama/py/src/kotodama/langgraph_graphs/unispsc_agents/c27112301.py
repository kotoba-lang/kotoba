from typing import TypedDict
from langgraph.graph import StateGraph, END

class BrandersState(TypedDict):
    temp_rating: int
    material_compliance: bool
    safety_check: bool

def validate_temp(state: BrandersState):
    return {'temp_rating': state.get('temp_rating', 0)}

def verify_safety(state: BrandersState):
    return {'safety_check': state.get('temp_rating', 0) < 500}

graph = StateGraph(BrandersState)
graph.add_node('validate', validate_temp)
graph.add_node('safety', verify_safety)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()
