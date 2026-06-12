from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    equipment_id: str
    calibration_status: bool
    safety_compliance: bool

def validate_specs(state: ProcurementState):
    state['calibration_status'] = True
    return state

def verify_safety(state: ProcurementState):
    state['safety_compliance'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', verify_safety)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
