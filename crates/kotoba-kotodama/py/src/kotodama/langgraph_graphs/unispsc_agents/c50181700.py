from typing import TypedDict
from langgraph.graph import StateGraph, END

class BakingSupplyState(TypedDict):
    item_name: str
    expiration_date: str
    safety_verified: bool

def validate_compliance(state: BakingSupplyState):
    # Business logic for baking supply shelf-life validation
    if not state.get('expiration_date'):
        return {'safety_verified': False}
    return {'safety_verified': True}

graph = StateGraph(BakingSupplyState)
graph.add_node('validate', validate_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
