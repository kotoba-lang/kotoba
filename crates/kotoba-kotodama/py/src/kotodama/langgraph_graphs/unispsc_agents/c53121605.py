from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoinPurseState(TypedDict):
    material: str
    quality_check_passed: bool
    approved: bool

def validate_material(state: CoinPurseState):
    # Business logic for material compliance
    return {"quality_check_passed": state.get("material") in ["leather", "nylon", "canvas"]}

def final_approval(state: CoinPurseState):
    return {"approved": state.get("quality_check_passed")}

graph_builder = StateGraph(CoinPurseState)
graph_builder.add_node("validate", validate_material)
graph_builder.add_node("approve", final_approval)
graph_builder.set_entry_point("validate")
graph_builder.add_edge("validate", "approve")
graph_builder.add_edge("approve", END)
graph = graph_builder.compile()
