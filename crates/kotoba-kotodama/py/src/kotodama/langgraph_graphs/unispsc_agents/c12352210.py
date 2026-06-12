from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CatalystProcessState(TypedDict):
    purity: float
    temp_celsius: float
    validation_logs: List[str]
    is_approved: bool

def validate_catalyst(state: CatalystProcessState):
    logs = state.get("validation_logs", [])
    if state.get("purity", 0) < 99.9:
        logs.append("Purity below threshold for high-performance usage.")
        return {"is_approved": False, "validation_logs": logs}
    logs.append("Catalyst purity verified.")
    return {"is_approved": True, "validation_logs": logs}

def stabilize_process(state: CatalystProcessState):
    if state.get("temp_celsius", 0) > 400:
        return {"validation_logs": state["validation_logs"] + ["Thermal instability detected"]}
    return {"validation_logs": state["validation_logs"] + ["Thermal stability within safety margins"]}

graph = StateGraph(CatalystProcessState)
graph.add_node("validate", validate_catalyst)
graph.add_node("stabilize", stabilize_process)
graph.set_entry_point("validate")
graph.add_edge("validate", "stabilize")
graph.add_edge("stabilize", END)
graph = graph.compile()
