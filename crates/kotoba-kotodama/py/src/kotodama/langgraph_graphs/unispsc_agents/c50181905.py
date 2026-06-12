from typing import TypedDict
from langgraph.graph import StateGraph, END

class BiscuitState(TypedDict):
    batch_id: str
    food_safety_passed: bool
    shelf_life_active: bool
    approved: bool

def validate_safety(state: BiscuitState) -> BiscuitState:
    state['food_safety_passed'] = True
    return state

def check_shelf_life(state: BiscuitState) -> BiscuitState:
    state['shelf_life_active'] = True
    return state

def finalize_approval(state: BiscuitState) -> BiscuitState:
    state['approved'] = state.get('food_safety_passed') and state.get('shelf_life_active')
    return state

graph = StateGraph(BiscuitState)
graph.add_node('safety_check', validate_safety)
graph.add_node('expiry_check', check_shelf_life)
graph.add_node('finalize', finalize_approval)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'expiry_check')
graph.add_edge('expiry_check', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
