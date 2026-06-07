from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GraphiteState(TypedDict):
    material_spec: dict
    validation_results: Annotated[Sequence[str], operator.add]
    status: str

def validate_material(state: GraphiteState):
    spec = state.get("material_spec", {})
    results = []
    if spec.get("purity_percentage", 0) < 99.0:
        results.append("Purity below threshold")
    return {"validation_results": results}

def check_compliance(state: GraphiteState):
    if len(state["validation_results"]) == 0:
        return {"status": "COMPLIANT"}
    return {"status": "FLAGGED"}

graph = StateGraph(GraphiteState)
graph.add_node("validate", validate_material)
graph.add_node("compliance", check_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()
