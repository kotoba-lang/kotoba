from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    assembly_id: str
    pressure_test_result: float
    weld_integrity_passed: bool
    final_status: str

def validate_weld(state: ProcessingState):
    # Simulate ultrasonic weld inspection logic
    state['weld_integrity_passed'] = state.get('pressure_test_result', 0) > 1.5
    return {"weld_integrity_passed": state['weld_integrity_passed']}

def update_status(state: ProcessingState):
    status = "APPROVED" if state['weld_integrity_passed'] else "REJECTED"
    return {"final_status": status}

graph = StateGraph(ProcessingState)
graph.add_node("validate", validate_weld)
graph.add_node("status", update_status)
graph.set_entry_point("validate")
graph.add_edge("validate", "status")
graph.add_edge("status", END)
graph = graph.compile()
