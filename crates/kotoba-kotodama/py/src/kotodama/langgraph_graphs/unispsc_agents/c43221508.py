from typing import TypedDict
from langgraph.graph import StateGraph, END

class BLFState(TypedDict):
    compatibility_check: bool
    config_verified: bool
    device_id: str

def validate_pbx_compatibility(state: BLFState) -> BLFState:
    state['compatibility_check'] = True
    return state

def verify_configuration(state: BLFState) -> BLFState:
    state['config_verified'] = True
    return state

graph = StateGraph(BLFState)
graph.add_node('validate_compatibility', validate_pbx_compatibility)
graph.add_node('verify_config', verify_configuration)
graph.set_entry_point('validate_compatibility')
graph.add_edge('validate_compatibility', 'verify_config')
graph.add_edge('verify_config', END)
graph = graph.compile()
