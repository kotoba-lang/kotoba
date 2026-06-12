from typing import TypedDict
from langgraph.graph import StateGraph, END

class FoodState(TypedDict):
    item_name: str
    quality_status: str
    inspection_passed: bool

def validate_food_safety(state: FoodState):
    print(f'Checking {state[item_name]} safety standards...')
    return {'quality_status': 'verified', 'inspection_passed': True}

def update_inventory(state: FoodState):
    print('Updating shelf-life data...')
    return {'quality_status': 'finalized'}

graph = StateGraph(FoodState)
graph.add_node('safety_check', validate_food_safety)
graph.add_node('inventory_log', update_inventory)
graph.add_edge('safety_check', 'inventory_log')
graph.add_edge('inventory_log', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
