from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MineralProcessState(TypedDict):
    material_id: str
    purity_check: bool
    safety_compliance: bool
    processing_steps: Annotated[Sequence[str], operator.add]

def validate_material(state: MineralProcessState):
    # Simulate purity check logic
    return {"purity_check": True}

def check_safety(state: MineralProcessState):
    # Simulate regulatory compliance check
    return {"safety_compliance": True}

def log_step(state: MineralProcessState):
    return {"processing_steps": ["validated", "safety_cleared"]}

workflow = StateGraph(MineralProcessState)
workflow.add_node("validate", validate_material)
workflow.add_node("safety", check_safety)
workflow.add_node("log", log_step)

workflow.set_entry_point("validate")
workflow.add_edge("validate", "safety")
workflow.add_edge("safety", "log")
workflow.add_edge("log", END)

graph = workflow.compile()
