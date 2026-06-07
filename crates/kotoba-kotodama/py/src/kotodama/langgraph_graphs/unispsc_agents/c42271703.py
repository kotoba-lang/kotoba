from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BlenderState(TypedDict):
    device_id: str
    calibration_data: dict
    approved: bool

def validate_calibration(state: BlenderState) -> BlenderState:
    data = state.get('calibration_data', {})
    state['approved'] = data.get('accuracy_rate', 0) > 0.98
    return state

def workflow_decision(state: BlenderState) -> str:
    return 'approved' if state['approved'] else 'rejected'

graph = StateGraph(BlenderState)
graph.add_node('validate', validate_calibration)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', workflow_decision, {'approved': END, 'rejected': END})
graph = graph.compile()
