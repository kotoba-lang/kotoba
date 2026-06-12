from langgraph.graph import StateGraph, END
from typing import TypedDict, List
class SurgicalProcurementState(TypedDict):
    tool_id: str
    material_compliance: bool
    is_sterile: bool
    validation_logs: List[str]

def validate_material(state: SurgicalProcurementState):
    state['material_compliance'] = True
    return state

def check_sterilization(state: SurgicalProcurementState):
    state['is_sterile'] = True
    return state

graph = StateGraph(SurgicalProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('sterilize_check', check_sterilization)
graph.add_edge('validate', 'sterilize_check')
graph.add_edge('sterilize_check', END)
graph.set_entry_point('validate')

graph = graph.compile()
