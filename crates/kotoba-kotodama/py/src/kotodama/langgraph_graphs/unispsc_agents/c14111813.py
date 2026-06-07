from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class State(TypedDict):
    commodity_code: str
    spec_requirements: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_spec(state: State) -> State:
    specs = state.get("spec_requirements", {})
    logs = []
    if specs.get("paper_weight_gsm", 0) < 60:
        logs.append("Low weight detected")
    return {"validation_log": logs, "is_compliant": True}

def update_inventory(state: State) -> State:
    return {"validation_log": ["Inventory updated for stationery"]}

builder = StateGraph(State)
builder.add_node("validate", validate_spec)
builder.add_node("inventory", update_inventory)
builder.add_edge("validate", "inventory")
builder.add_edge("inventory", END)
builder.set_entry_point("validate")
graph = builder.compile()
