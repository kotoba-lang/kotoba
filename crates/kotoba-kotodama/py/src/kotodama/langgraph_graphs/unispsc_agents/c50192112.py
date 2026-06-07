from typing import TypedDict
from langgraph.graph import StateGraph, END

class PopcornState(TypedDict):
    batch_id: str
    expiry_date: str
    is_compliant: bool

def validate_popcorn(state: PopcornState):
    # Simulate validation logic for food safety
    compliance = 'expiry_date' in state and 'batch_id' in state
    return {'is_compliant': compliance}

graph = StateGraph(PopcornState)
graph.add_node('validator', validate_popcorn)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
