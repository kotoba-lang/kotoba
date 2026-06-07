from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FlashCardState(TypedDict):
    content: str
    specs: dict
    approved: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_content(state: FlashCardState):
    log = []
    if not state.get('specs', {}).get('material'):
        log.append("Missing material spec")
    return {"validation_log": log, "approved": len(log) == 0}

def approval_node(state: FlashCardState):
    return {"approved": True}

graph = StateGraph(FlashCardState)
graph.add_node("validate", validate_content)
graph.add_node("approve", approval_node)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
