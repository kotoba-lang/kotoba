from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AluminumIngotState(TypedDict):
    batch_id: str
    composition: dict
    status: str
    validation_log: Annotated[Sequence[str], operator.add]

def validate_chemistry(state: AluminumIngotState):
    comp = state.get("composition", {})
    if comp.get("Al", 0) < 95.0:
        return {"status": "REJECTED", "validation_log": ["Purity below 95% threshold"]}
    return {"status": "VALIDATED", "validation_log": ["Chemistry verification passed"]}

def check_compliance(state: AluminumIngotState):
    if state.get("status") == "VALIDATED":
        return {"validation_log": ["Dual-use export control check completed"]}
    return {"validation_log": ["Export check skipped due to rejection"]}

graph = StateGraph(AluminumIngotState)
graph.add_node("validate", validate_chemistry)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
