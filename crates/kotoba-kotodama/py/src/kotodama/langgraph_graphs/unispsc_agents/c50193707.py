from langgraph.graph import StateGraph, END
from typing import TypedDict

class FoodProcurementState(TypedDict):
    commodity: str
    inspection_passed: bool
    storage_compliant: bool

def validate_food_safety(state: FoodProcurementState) -> FoodProcurementState:
    # Simulate quality control logic for preserved fruit
    state['inspection_passed'] = True
    return state

def check_cold_chain(state: FoodProcurementState) -> FoodProcurementState:
    # Verify storage requirements
    state['storage_compliant'] = True
    return state

graph = StateGraph(FoodProcurementState)
graph.add_node('validate', validate_food_safety)
graph.add_node('check_storage', check_cold_chain)
graph.set_entry_point('validate')
graph.add_edge('validate', 'check_storage')
graph.add_edge('check_storage', END)
graph = graph.compile()
