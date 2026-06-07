from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class FeedProcessingState(TypedDict):
    batch_id: str
    quality_passed: bool
    compliance_checks: Annotated[list[str], operator.add]

def validate_composition(state: FeedProcessingState):
    # Simulate nutritional analysis
    return {"quality_passed": True, "compliance_checks": ["composition_verified"]}

def check_regulatory_compliance(state: FeedProcessingState):
    return {"compliance_checks": ["fao_standards_met"]}

def build_graph():
    graph = StateGraph(FeedProcessingState)
    graph.add_node("validate", validate_composition)
    graph.add_node("regulatory", check_regulatory_compliance)
    graph.set_entry_point("validate")
    graph.add_edge("validate", "regulatory")
    graph.add_edge("regulatory", END)
    return graph.compile()

graph = build_graph()
