from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class PaperProcurementState(TypedDict):
    commodity_code: str
    spec_requirements: dict
    validation_logs: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_paper_spec(state: PaperProcurementState):
    spec = state.get("spec_requirements", {})
    logs = []
    compliant = True
    if spec.get("gsm_weight", 0) < 60:
        logs.append("Error: Paper weight below minimum standard for commercial grade.")
        compliant = False
    return {"validation_logs": logs, "is_compliant": compliant}

def route_procurement(state: PaperProcurementState):
    return "process" if state["is_compliant"] else END

def finalize_order(state: PaperProcurementState):
    return {"validation_logs": ["Order finalized for production."]}

graph = StateGraph(PaperProcurementState)
graph.add_node("validate", validate_paper_spec)
graph.add_node("process", finalize_order)
graph.set_entry_point("validate")
graph.add_conditional_edges("validate", route_procurement)
graph.add_edge("process", END)
graph = graph.compile()
