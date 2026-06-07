from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class PaperProcurementState(TypedDict):
    commodity_code: str
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_fiber_source(state: PaperProcurementState):
    # Simulate FSC/PEFC validation
    return {"validation_logs": ["Verified fiber source sustainability certification."]}

def check_physical_specs(state: PaperProcurementState):
    # Simulate GSM and moisture checks
    return {"validation_logs": ["Checked gsm weight and moisture content against specs."], "is_compliant": True}

graph = StateGraph(PaperProcurementState)
graph.add_node("validate_source", validate_fiber_source)
graph.add_node("check_specs", check_physical_specs)
graph.set_entry_point("validate_source")
graph.add_edge("validate_source", "check_specs")
graph.add_edge("check_specs", END)
graph = graph.compile()
