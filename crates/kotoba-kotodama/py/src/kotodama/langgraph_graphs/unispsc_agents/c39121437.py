from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CollectorState(TypedDict):
    material_spec: str
    wear_test_passed: bool
    conductivity_score: float

async def validate_specs(state: CollectorState):
    # Business logic for validating collector shoe physical specifications
    is_valid = state['wear_test_passed'] and state['conductivity_score'] > 95.0
    return {"material_spec": "Validated" if is_valid else "Rejected"}

workflow = StateGraph(CollectorState)
workflow.add_node("validate", validate_specs)
workflow.set_entry_point("validate")
workflow.add_edge("validate", END)
graph = workflow.compile()
