from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ResourceState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    compliance_status: bool
    history: Annotated[List[str], add_messages]

def validate_resource_purity(state: ResourceState):
    # Simulate chemical assay validation
    metrics = state.get("quality_metrics", {})
    purity = metrics.get("purity_level", 0)
    return {"compliance_status": purity > 0.95, "history": [f"Purity check: {purity}"]}

def check_sanctions(state: ResourceState):
    # Simulated compliance lookup
    return {"history": ["Origin verification complete for sanctions compliance"]}

graph = StateGraph(ResourceState)
graph.add_node("validate", validate_resource_purity)
graph.add_node("compliance", check_sanctions)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()
