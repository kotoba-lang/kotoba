from langgraph.graph import StateGraph, END
from typing import TypedDict

class MotionSensorState(TypedDict):
    model_number: str
    spec_compliance: bool
    export_control_check: bool

def validate_specs(state: MotionSensorState):
    print(f'Validating specs for {state.get('model_number')}')
    return {'spec_compliance': True}

def export_compliance(state: MotionSensorState):
    print('Checking dual-use export control regulations.')
    return {'export_control_check': True}

graph = StateGraph(MotionSensorState)
graph.add_node('validate', validate_specs)
graph.add_node('export', export_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()
