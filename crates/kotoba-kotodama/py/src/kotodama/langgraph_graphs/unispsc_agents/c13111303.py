from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ResourceState(TypedDict):
    sensor_data: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_safe: bool

def validate_sensor(state: ResourceState):
    data = state.get('sensor_data', {})
    status = data.get('pressure', 0) < 5000
    return {'validation_log': ['Pressure check passed' if status else 'Pressure alarm'], 'is_safe': status}

def alert_operator(state: ResourceState):
    return {'validation_log': ['Operator notified of critical status']}

def decide_next(state: ResourceState):
    return 'alert' if not state['is_safe'] else END

graph = StateGraph(ResourceState)
graph.add_node('validate', validate_sensor)
graph.add_node('alert', alert_operator)
graph.add_edge('validate', 'alert')
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', decide_next)
graph.add_edge('alert', END)
graph = graph.compile()
