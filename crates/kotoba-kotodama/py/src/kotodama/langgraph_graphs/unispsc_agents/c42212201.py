from typing import TypedDict
from langgraph.graph import StateGraph, END

class PillDeviceState(TypedDict):
    device_type: str
    compliance_check: bool
    safety_validation: bool

def validate_specs(state: PillDeviceState):
    print('Validating medical device specifications...')
    state['compliance_check'] = True
    return state

def safety_audit(state: PillDeviceState):
    print('Performing mechanical safety audit for sharp components...')
    state['safety_validation'] = True
    return state

graph = StateGraph(PillDeviceState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
