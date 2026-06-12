from typing import TypedDict
from langgraph.graph import StateGraph, END

class VentilatorSensorState(TypedDict):
    temp_accuracy: float
    iso_compliant: bool
    validation_score: int

def validate_sensor_specs(state: VentilatorSensorState):
    score = 10 if state.get('iso_compliant') and state.get('temp_accuracy', 0) < 0.5 else 0
    return {'validation_score': score}

def approval_node(state: VentilatorSensorState):
    return {'validation_score': state['validation_score'] + 5}

graph = StateGraph(VentilatorSensorState)
graph.add_node('validate', validate_sensor_specs)
graph.add_node('approve', approval_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
