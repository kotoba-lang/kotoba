from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class StationeryState(TypedDict):
    order_items: Annotated[list, operator.add]
    validation_logs: Annotated[list, operator.add]
    is_compliant: bool

def validate_paper_spec(state: StationeryState):
    items = state.get("order_items", [])
    logs = ["Validation started for stationery order."]
    compliant = True
    for item in items:
        if item.get("weight", 0) < 60:
            logs.append(f"Warning: {item.get('name')} below standard 60gsm.")
            compliant = False
    return {"validation_logs": logs, "is_compliant": compliant}

def process_inventory_update(state: StationeryState):
    return {"validation_logs": ["Inventory database synchronized."]}

graph = StateGraph(StationeryState)
graph.add_node("validate", validate_paper_spec)
graph.add_node("inventory", process_inventory_update)
graph.set_entry_point("validate")
graph.add_edge("validate", "inventory")
graph.add_edge("inventory", END)
graph = graph.compile()
