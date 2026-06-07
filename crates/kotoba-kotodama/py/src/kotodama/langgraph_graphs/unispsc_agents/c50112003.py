from typing import TypedDict
from langgraph.graph import StateGraph, END

class MeatProcurementState(TypedDict):
    product_id: str
    quality_passed: bool
    batch_code: str
    shelf_life_status: str

def validate_expiry(state: MeatProcurementState):
    # logic for shelf life validation
    state['shelf_life_status'] = 'validated'
    return state

def verify_food_safety(state: MeatProcurementState):
    # logic for ISO 22000 verification
    state['quality_passed'] = True
    return state

graph = StateGraph(MeatProcurementState)
graph.add_node('validate_expiry', validate_expiry)
graph.add_node('verify_safety', verify_food_safety)
graph.add_edge('validate_expiry', 'verify_safety')
graph.add_edge('verify_safety', END)
graph.set_entry_point('validate_expiry')
graph = graph.compile()
