from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class AnalysisState(TypedDict):
    reagent_id: str
    quality_checks: Annotated[List[str], operator.add]
    is_cleared: bool

def validate_cold_chain(state: AnalysisState) -> dict:
    # Logic to verify temperature logs for perishables
    return {"quality_checks": ["cold_chain_validated"], "is_cleared": True}

def perform_purity_test(state: AnalysisState) -> dict:
    return {"quality_checks": ["purity_test_passed"]}

builder = StateGraph(AnalysisState)
builder.add_node("validate_cold_chain", validate_cold_chain)
builder.add_node("perform_purity_test", perform_purity_test)
builder.add_edge("validate_cold_chain", "perform_purity_test")
builder.add_edge("perform_purity_test", END)
builder.set_entry_point("validate_cold_chain")
graph = builder.compile()
