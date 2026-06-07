from typing import TypedDict
from langgraph.graph import StateGraph, END

class ScooterState(TypedDict):
    model_id: str
    battery_verified: bool
    safety_rating: float
    approved: bool

def validate_battery(state: ScooterState):
    # Simulate battery certification check
    return {'battery_verified': True}

def classify_safety(state: ScooterState):
    # Simulate safety protocol check
    return {'safety_rating': 4.5, 'approved': True}

workflow = StateGraph(ScooterState)
workflow.add_node('battery_check', validate_battery)
workflow.add_node('safety_check', classify_safety)
workflow.set_entry_point('battery_check')
workflow.add_edge('battery_check', 'safety_check')
workflow.add_edge('safety_check', END)
graph = workflow.compile()
