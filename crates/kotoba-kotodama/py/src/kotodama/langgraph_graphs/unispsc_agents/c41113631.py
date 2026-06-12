from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OhmmeterState(TypedDict):
    measurement_data: dict
    validation_logs: List[str]
    calibration_compliant: bool

def validate_specs(state: OhmmeterState):
    # Simulate validation logic for resistance test data
    data = state.get('measurement_data', {})
    state['validation_logs'] = ['Range check PASSED', 'Accuracy check PASSED']
    state['calibration_compliant'] = True
    return state

def approve_procurement(state: OhmmeterState):
    return {'validation_logs': state['validation_logs'] + ['Procurement approved']}

graph = StateGraph(OhmmeterState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approve_procurement)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')

graph = graph.compile()
