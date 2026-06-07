from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class OreState(TypedDict):
    raw_data: dict
    analysis_results: list[str]
    validation_passed: bool

def analyze_ore_quality(state: OreState):
    # Simulate chemical analysis logic
    results = ["Purity check: 99.8%", "Trace elements: compliant"]
    return {"analysis_results": results}

def validate_compliance(state: OreState):
    # Simulate regulatory/export control check
    return {"validation_passed": True}

graph = StateGraph(OreState)
graph.add_node("analyze", analyze_ore_quality)
graph.add_node("validate", validate_compliance)
graph.add_edge("analyze", "validate")
graph.add_edge("validate", END)
graph.set_entry_point("analyze")
graph = graph.compile()
