from typing import TypedDict
from langgraph.graph import StateGraph, END

class BoardAidState(TypedDict):
    item_name: str
    magnetic_force_n: float
    safety_verified: bool

def validate_magnets(state: BoardAidState):
    if state.get("magnetic_force_n", 0) < 5:
        return {"safety_verified": False}
    return {"safety_verified": True}

builder = StateGraph(BoardAidState)
builder.add_node("validate", validate_magnets)
builder.set_entry_point("validate")
builder.add_edge("validate", END)
graph = builder.compile()
