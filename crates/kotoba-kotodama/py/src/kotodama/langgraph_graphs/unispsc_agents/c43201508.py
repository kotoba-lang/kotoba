from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class InfraState(TypedDict):
    task_list: Annotated[Sequence[str], operator.add]
    validation_errors: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def provision_node(state: InfraState):
    return {"task_list": ["Provisioning Infrastructure Node..."], "is_compliant": True}

def validate_node(state: InfraState):
    return {"task_list": ["Validating Security Standards..."], "validation_errors": []}

graph = StateGraph(InfraState)
graph.add_node("provision", provision_node)
graph.add_node("validate", validate_node)
graph.set_entry_point("provision")
graph.add_edge("provision", "validate")
graph.add_edge("validate", END)
graph = graph.compile()
