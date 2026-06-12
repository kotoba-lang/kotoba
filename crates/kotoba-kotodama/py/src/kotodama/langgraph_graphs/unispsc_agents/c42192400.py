from typing import TypedDict
from langgraph.graph import StateGraph, END

class EquipmentState(TypedDict):
    equipment_id: str
    safety_check_passed: bool
    validation_log: list

def validate_medical_specs(state: EquipmentState):
    # Simulate multi-step clinical standard validation
    passed = True
    return {"safety_check_passed": passed, "validation_log": ["Compliance audit: PASSED"]}

def update_inventory(state: EquipmentState):
    return {"validation_log": state["validation_log"] + ["Inventory updated"]}

graph = StateGraph(EquipmentState)
graph.add_node("validate", validate_medical_specs)
graph.add_node("inventory", update_inventory)
graph.set_entry_point("validate")
graph.add_edge("validate", "inventory")
graph.add_edge("inventory", END)
graph = graph.compile()
