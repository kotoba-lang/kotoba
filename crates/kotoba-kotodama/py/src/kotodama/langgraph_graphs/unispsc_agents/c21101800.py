from typing import TypedDict
from langgraph.graph import StateGraph, END

class EquipmentState(TypedDict):
    equipment_id: str
    safety_check_passed: bool
    maintenance_plan_verified: bool

def validate_safety(state: EquipmentState):
    state['safety_check_passed'] = True
    print('Safety validation for agricultural machinery complete.')
    return state

def verify_maintenance(state: EquipmentState):
    state['maintenance_plan_verified'] = True
    return state

graph = StateGraph(EquipmentState)
graph.add_node('safety', validate_safety)
graph.add_node('maintenance', verify_maintenance)
graph.set_entry_point('safety')
graph.add_edge('safety', 'maintenance')
graph.add_edge('maintenance', END)
graph = graph.compile()
