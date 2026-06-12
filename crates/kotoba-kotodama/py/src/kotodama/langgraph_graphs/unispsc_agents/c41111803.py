from langgraph.graph import StateGraph, END
from typing import TypedDict
class InspectionState(TypedDict):
    equipment_id: str
    calibration_status: bool
    test_results: dict
    approved: bool

def validate_calibration(state: InspectionState):
    state['calibration_status'] = True
    return state

def perform_inspection(state: InspectionState):
    state['test_results'] = {'status': 'passed'}
    state['approved'] = True
    return state

graph = StateGraph(InspectionState)
graph.add_node('validate', validate_calibration)
graph.add_node('inspect', perform_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
