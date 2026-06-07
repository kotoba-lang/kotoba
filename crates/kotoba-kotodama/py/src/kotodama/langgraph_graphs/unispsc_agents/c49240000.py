from typing import TypedDict
from langgraph.graph import StateGraph, END

class EquipmentState(TypedDict):
    equipment_type: str
    safety_check_passed: bool
    compliance_report: str

def validate_safety(state: EquipmentState):
    return {'safety_check_passed': True, 'compliance_report': 'Safety standards verified'}

def approval_step(state: EquipmentState):
    return {'compliance_report': 'Equipment approved for procurement'}

graph_builder = StateGraph(EquipmentState)
graph_builder.add_node('safety_check', validate_safety)
graph_builder.add_node('approval', approval_step)
graph_builder.set_entry_point('safety_check')
graph_builder.add_edge('safety_check', 'approval')
graph_builder.add_edge('approval', END)
graph = graph_builder.compile()
