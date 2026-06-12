from typing import TypedDict
from langgraph.graph import StateGraph, END

class AlarmState(TypedDict):
    equipment_id: str
    validation_passed: bool
    alert_config: dict

def validate_telephony_device(state: AlarmState):
    # Simulate CAD/Spec validation logic
    state['validation_passed'] = bool(state.get('equipment_id'))
    return state

def check_compliance(state: AlarmState):
    # Simulate regulatory compliance check
    return {'validation_passed': state['validation_passed']}

graph_builder = StateGraph(AlarmState)
graph_builder.add_node('validate', validate_telephony_device)
graph_builder.add_node('compliance', check_compliance)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', 'compliance')
graph_builder.add_edge('compliance', END)
graph = graph_builder.compile()
