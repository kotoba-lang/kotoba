from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class EndpointState(TypedDict):
    device_id: str
    config_tasks: Annotated[Sequence[str], operator.add]
    validation_errors: Annotated[Sequence[str], operator.add]

def validate_policy(state: EndpointState):
    # Simulate policy compliance check
    return {"config_tasks": ["Check OS Version"], "validation_errors": []}

def deploy_configuration(state: EndpointState):
    # Simulate deployment logic
    return {"config_tasks": ["Push Software Package"]}

workflow = StateGraph(EndpointState)
workflow.add_node("validate", validate_policy)
workflow.add_node("deploy", deploy_configuration)
workflow.add_edge("validate", "deploy")
workflow.set_entry_point("validate")
workflow.add_edge("deploy", END)
graph = workflow.compile()
