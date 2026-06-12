from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
class VendingState(TypedDict):
    serial_number: str
    sanitation_status: bool
    inventory_level: int
def check_compliance(state: VendingState):
    state['sanitation_status'] = True
    return state
def update_inventory(state: VendingState):
    state['inventory_level'] = 100
    return state
graph = StateGraph(VendingState)
graph.add_node('compliance', check_compliance)
graph.add_node('inventory', update_inventory)
graph.add_edge('compliance', 'inventory')
graph.add_edge('inventory', END)
graph.set_entry_point('compliance')
graph = graph.compile()
