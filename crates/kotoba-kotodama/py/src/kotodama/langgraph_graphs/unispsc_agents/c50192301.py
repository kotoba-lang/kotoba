from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DessertState(TypedDict):
    item_name: str
    expiry_date: str
    requires_cold_chain: bool
    compliance_cleared: bool

def validate_food_safety(state: DessertState):
    # Basic validation for perishables
    if state.get('expiry_date') and state.get('requires_cold_chain'):
        state['compliance_cleared'] = True
    else:
        state['compliance_cleared'] = False
    return state

graph = StateGraph(DessertState)
graph.add_node('safety_check', validate_food_safety)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
