from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ContactCenterState(TypedDict):
    requirements: dict
    validation_errors: List[str]
    is_compliant: bool

def validate_specs(state: ContactCenterState):
    errors = []
    if "data_residency" not in state.get("requirements", {}):
        errors.append("Missing data residency specification")
    return {"validation_errors": errors, "is_compliant": len(errors) == 0}

def deploy_config(state: ContactCenterState):
    print("Deploying contact center configuration...")
    return state

graph = StateGraph(ContactCenterState)
graph.add_node("validate", validate_specs)
graph.add_node("deploy", deploy_config)
graph.set_entry_point("validate")
graph.add_edge("validate", "deploy")
graph.add_edge("deploy", END)
graph = graph.compile()
