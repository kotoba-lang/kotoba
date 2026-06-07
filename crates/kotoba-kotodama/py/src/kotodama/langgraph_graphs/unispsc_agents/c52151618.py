from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    material: str
    dimensions: dict
    is_food_safe: bool

def validate_materials(state: KitchenwareState):
    print(f'Validating material: {state.get("material")}')
    return {"is_food_safe": state.get("material") in ["Beechwood", "Bamboo"]}

def check_dimensions(state: KitchenwareState):
    print(f'Checking dimensions: {state.get("dimensions")}')
    return state

graph = StateGraph(KitchenwareState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("check_dimensions", check_dimensions)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "check_dimensions")
graph.add_edge("check_dimensions", END)
graph = graph.compile()
