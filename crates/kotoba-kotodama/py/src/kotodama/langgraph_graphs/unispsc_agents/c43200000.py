from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ICTProcurementState(TypedDict):
    items: Annotated[Sequence[str], operator.add]
    validation_logs: Annotated[Sequence[str], operator.add]
    status: str

def validate_hardware_spec(state: ICTProcurementState) -> ICTProcurementState:
    return {"validation_logs": ["Validated technical specifications against ICT infrastructure requirements."]}

def check_compliance(state: ICTProcurementState) -> ICTProcurementState:
    return {"validation_logs": ["Verified export control and energy compliance status."]}

graph = StateGraph(ICTProcurementState)
graph.add_node("validate", validate_hardware_spec)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
