from typing import TypedDict
from langgraph.graph import StateGraph, END

class CheeseState(TypedDict):
    product_name: str
    safety_compliance: bool
    is_perishable: bool

def validate_food_safety(state: CheeseState):
    state['safety_compliance'] = True
    return state

def check_storage_requirements(state: CheeseState):
    state['is_perishable'] = True
    return state

workflow = StateGraph(CheeseState)
workflow.add_node("safety_check", validate_food_safety)
workflow.add_node("storage_check", check_storage_requirements)
workflow.set_entry_point("safety_check")
workflow.add_edge("safety_check", "storage_check")
workflow.add_edge("storage_check", END)
graph = workflow.compile()
