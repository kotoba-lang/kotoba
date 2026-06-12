from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoagulationState(TypedDict):
    item_id: str
    expiration_date: str
    stability_data: dict
    is_validated: bool

def validate_reagent(state: CoagulationState):
    # Simulate regulatory validation logic for IVD products
    if state.get("expiration_date") and state.get("stability_data"):
        return {"is_validated": True}
    return {"is_validated": False}

def process_shipment(state: CoagulationState):
    if state["is_validated"]:
        print(f"Processing secure shipment for item {state['item_id']}")
    return state

graph = StateGraph(CoagulationState)
graph.add_node("validate", validate_reagent)
graph.add_node("ship", process_shipment)
graph.set_entry_point("validate")
graph.add_edge("validate", "ship")
graph.add_edge("ship", END)
graph = graph.compile()
