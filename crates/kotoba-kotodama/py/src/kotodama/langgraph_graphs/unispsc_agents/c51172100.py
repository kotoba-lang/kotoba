from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MedicationState(TypedDict):
    medication_name: str
    regulatory_compliant: bool
    safety_check_passed: bool
    validation_log: List[str]

def validate_compliance(state: MedicationState):
    # Simulate regulatory check
    return {"regulatory_compliant": True, "validation_log": ["Compliance check completed"]}

def safety_gate(state: MedicationState):
    # Simulate clinical safety criteria
    return {"safety_check_passed": True, "validation_log": state["validation_log"] + ["Safety check passed"]}

graph = StateGraph(MedicationState)
graph.add_node("compliance", validate_compliance)
graph.add_node("safety", safety_gate)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "safety")
graph.add_edge("safety", END)
graph = graph.compile()
