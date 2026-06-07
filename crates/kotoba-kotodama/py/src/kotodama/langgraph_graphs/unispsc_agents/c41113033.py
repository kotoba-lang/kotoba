from typing import TypedDict
from langgraph.graph import StateGraph, END

class VolumeMeasureState(TypedDict):
    specification: dict
    validation_status: bool
    error_log: list

def validate_specs(state: VolumeMeasureState):
    specs = state.get('specification', {})
    required = ['accuracy_class', 'calibration_date']
    missing = [f for f in required if f not in specs]
    return {'validation_status': len(missing) == 0, 'error_log': missing}

def route_by_validation(state: VolumeMeasureState):
    return 'process' if state['validation_status'] else END

graph = StateGraph(VolumeMeasureState)
graph.add_node('validate', validate_specs)
graph.add_node('process', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()
