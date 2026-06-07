from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class BariteState(TypedDict):
    purity_test_results: dict
    compliance_checks: list
    shipping_logs: list

def validate_purity(state: BariteState) -> BariteState:
    # Logic to validate barium sulfate content >= 90%
    return state

def check_compliance(state: BariteState) -> BariteState:
    # Logic for heavy metal toxicity and regulatory safety
    return state

workflow = StateGraph(BariteState)
workflow.add_node("validate_purity", validate_purity)
workflow.add_node("check_compliance", check_compliance)
workflow.set_entry_point("validate_purity")
workflow.add_edge("validate_purity", "check_compliance")
workflow.add_edge("check_compliance", END)

graph = workflow.compile()
