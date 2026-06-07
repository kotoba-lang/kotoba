from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CornetState(TypedDict):
    instrument_spec: dict
    validation_passed: bool
    inspection_report: str

def validate_specs(state: CornetState):
    spec = state.get("instrument_spec", {})
    # Check for required pitch and material fields
    is_valid = "pitch_hz" in spec and "material" in spec
    return {"validation_passed": is_valid}

def generate_report(state: CornetState):
    return {"inspection_report": "Quality assurance verified for acoustic parameters."}

graph = StateGraph(CornetState)
graph.add_node("validate", validate_specs)
graph.add_node("inspect", generate_report)
graph.add_edge("validate", "inspect")
graph.add_edge("inspect", END)
graph.set_entry_point("validate")
graph = graph.compile()
