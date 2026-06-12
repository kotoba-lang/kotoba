from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    compliance_docs: bool
    is_approved: bool

def validate_sterilization_supplies(state: ProcurementState):
    # Business logic for medical labeling verification
    compliance = state.get('compliance_docs', False)
    return {'is_approved': compliance}

def build_graph():
    workflow = StateGraph(ProcurementState)
    workflow.add_node('validate', validate_sterilization_supplies)
    workflow.set_entry_point('validate')
    workflow.add_edge('validate', END)
    return workflow.compile()

graph = build_graph()
