from typing import TypedDict
from langgraph.graph import StateGraph, END
class BarStockState(TypedDict):
    material: str
    solvent_type: str
    pressure_class: float
    validation_passed: bool
def validate_material(state: BarStockState):
    valid = state.get("material") in ["PVC", "CPVC", "ABS"]
    return {"validation_passed": valid}
def check_pressure(state: BarStockState):
    pressure = state.get("pressure_class", 0)
    return {"validation_passed": pressure > 0}
graph = StateGraph(BarStockState)
graph.add_node("validate", validate_material)
graph.add_node("pressure_check", check_pressure)
graph.add_edge("validate", "pressure_check")
graph.add_edge("pressure_check", END)
graph.set_entry_point("validate")
graph = graph.compile()
