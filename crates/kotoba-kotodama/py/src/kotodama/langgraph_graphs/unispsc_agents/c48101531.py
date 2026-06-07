from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    item_name: str
    material: str
    is_food_grade: bool
    validation_error: str

def validate_material(state: KitchenwareState):
    if state.get("material") != "304 stainless":
        return {"validation_error": "Material must be 304 food-grade stainless."}
    return {"is_food_grade": True}

graph = StateGraph(KitchenwareState)
graph.add_node("validate", validate_material)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()
