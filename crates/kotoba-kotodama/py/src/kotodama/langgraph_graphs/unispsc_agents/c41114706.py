from typing import TypedDict
from langgraph.graph import StateGraph, END

class WoodTestState(TypedDict):
    instrument_type: str
    calibration_date: str
    is_compliant: bool

def validate_instrument(state: WoodTestState):
    # Perform specific logic for wood testing instrument compliance
    return {"is_compliant": state.get("calibration_date") is not None}

def router(state: WoodTestState):
    return "VALIDATE" if state.get("instrument_type") else END

graph = StateGraph(WoodTestState)
graph.add_node("VALIDATE", validate_instrument)
graph.set_entry_point("VALIDATE")
graph.add_edge("VALIDATE", END)
graph = graph.compile()
