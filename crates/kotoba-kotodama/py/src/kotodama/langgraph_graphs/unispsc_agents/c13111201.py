from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class IronOreState(TypedDict):
    purity_check_passed: bool
    impurity_report: dict
    workflow_status: str

def validate_ore_quality(state: IronOreState):
    # Simulate chemical analysis logic
    iron_content = 65.0
    return {"purity_check_passed": iron_content > 60.0, "workflow_status": "quality_validated"}

def process_logistics(state: IronOreState):
    return {"workflow_status": "logistics_ready"}

graph = StateGraph(IronOreState)
graph.add_node("validate", validate_ore_quality)
graph.add_node("logistics", process_logistics)
graph.set_entry_point("validate")
graph.add_edge("validate", "logistics")
graph.add_edge("logistics", END)
graph = graph.compile()
