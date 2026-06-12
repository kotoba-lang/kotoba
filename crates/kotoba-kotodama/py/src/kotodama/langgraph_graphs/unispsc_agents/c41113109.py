from typing import TypedDict
from langgraph.graph import StateGraph, END

class OrsatState(TypedDict):
    equipment_id: str
    calibration_status: bool
    validation_error: str

def validate_specs(state: OrsatState):
    # Simulate CAD or spec validation for chemical analysis equipment
    if not state.get('calibration_status'):
        return {'validation_error': 'Calibration certificate missing'}
    return {'validation_error': 'None'}

def route_by_validation(state: OrsatState):
    return 'end' if state['validation_error'] == 'None' else 'end'

graph = StateGraph(OrsatState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
