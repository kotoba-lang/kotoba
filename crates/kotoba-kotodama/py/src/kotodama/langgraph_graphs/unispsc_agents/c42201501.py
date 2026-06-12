from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CTInstallState(TypedDict):
    site_id: str
    shielding_pass: bool
    power_verified: bool
    installation_complete: bool
    errors: List[str]

def validate_site(state: CTInstallState):
    return {"shielding_pass": True, "power_verified": True}

def perform_install(state: CTInstallState):
    return {"installation_complete": True}

graph = StateGraph(CTInstallState)
graph.add_node("validate_site", validate_site)
graph.add_node("perform_install", perform_install)
graph.set_entry_point("validate_site")
graph.add_edge("validate_site", "perform_install")
graph.add_edge("perform_install", END)
graph = graph.compile()
