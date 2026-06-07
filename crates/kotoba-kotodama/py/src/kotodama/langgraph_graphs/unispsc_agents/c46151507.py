from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class QueueSystemState(TypedDict):
    requirements: List[str]
    compliance_checked: bool
    final_solution: str

def validate_tech_specs(state: QueueSystemState):
    return {"compliance_checked": True}

def generate_config(state: QueueSystemState):
    return {"final_solution": "Queuing_System_Config_001"}

graph = StateGraph(QueueSystemState)
graph.add_node("validate", validate_tech_specs)
graph.add_node("config", generate_config)
graph.add_edge("validate", "config")
graph.add_edge("config", END)
graph.set_entry_point("validate")
graph = graph.compile()
