from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class SensorState(TypedDict):
    sensor_id: str
    config: dict
    validation_log: List[str]

def validate_specs(state: SensorState) -> SensorState:
    config = state.get('config', {})
    logs = []
    if config.get('detection_range_mm', 0) <= 0:
        logs.append('Invalid detection range')
    state['validation_log'] = logs
    return state

def check_compliance(state: SensorState) -> str:
    if state.get('validation_log'):
        return 'REJECT'
    return 'APPROVE'

graph = StateGraph(SensorState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', check_compliance, {'APPROVE': END, 'REJECT': END})
graph = graph.compile()
