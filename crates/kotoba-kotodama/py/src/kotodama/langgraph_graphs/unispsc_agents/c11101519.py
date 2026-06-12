from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystProcessState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    process_steps: Annotated[Sequence[str], operator.add]

def validate_purity(state: CatalystProcessState) -> dict:
    # Simulate analytical chemistry validation logic
    is_pure = True
    return {"purity_check": is_pure}

def check_safety_compliance(state: CatalystProcessState) -> dict:
    # Verify dual-use and dangerous goods compliance
    return {"safety_clearance": True}

def route_process(state: CatalystProcessState) -> str:
    if not state["purity_check"] or not state["safety_clearance"]:
        return "end"
    return "process_execution"

workflow = StateGraph(CatalystProcessState)
workflow.add_node("validate", validate_purity)
workflow.add_node("safety", check_safety_compliance)
workflow.add_node("process_execution", lambda x: {"process_steps": ["Optimization Initiated"]})

workflow.set_entry_point("validate")
workflow.add_edge("validate", "safety")
workflow.add_conditional_edges("safety", route_process, {"end": END, "process_execution": "process_execution"})
workflow.add_edge("process_execution", END)

graph = workflow.compile()
