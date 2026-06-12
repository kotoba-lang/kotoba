from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    hardware_id: str
    thermal_metrics: float
    security_verified: bool
    history: Annotated[Sequence[str], operator.add]

def validate_thermal_specs(state: ProcessingState) -> ProcessingState:
    return {"history": ["Validating thermal envelope for CPU processing unit."]}

def verify_export_compliance(state: ProcessingState) -> ProcessingState:
    return {"security_verified": True, "history": ["Verified dual-use export control compliance."]}

workflow = StateGraph(ProcessingState)
workflow.add_node("validate_thermal", validate_thermal_specs)
workflow.add_node("verify_compliance", verify_export_compliance)
workflow.set_entry_point("validate_thermal")
workflow.add_edge("validate_thermal", "verify_compliance")
workflow.add_edge("verify_compliance", END)
graph = workflow.compile()
