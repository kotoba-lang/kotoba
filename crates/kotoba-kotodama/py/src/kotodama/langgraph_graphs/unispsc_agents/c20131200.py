from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MiningPartsState(TypedDict):
    part_request: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_part_specs(state: MiningPartsState):
    log = "Validating compatibility and material specs against industry standards."
    return {"validation_log": [log], "is_approved": True}

def check_export_compliance(state: MiningPartsState):
    log = "Running dual-use export control checks on part components."
    return {"validation_log": [log]}

graph = StateGraph(MiningPartsState)
graph.add_node("validate", validate_part_specs)
graph.add_node("compliance", check_export_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
