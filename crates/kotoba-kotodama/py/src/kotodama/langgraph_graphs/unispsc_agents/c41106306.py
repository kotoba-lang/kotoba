from typing import TypedDict
from langgraph.graph import StateGraph, END

class PCRBufferState(TypedDict):
    purity_validated: bool
    temp_control_check: bool
    batch_number: str

def validate_buffer_purity(state: PCRBufferState):
    state['purity_validated'] = True
    return state

def verify_storage_requirements(state: PCRBufferState):
    state['temp_control_check'] = True
    return state

graph = StateGraph(PCRBufferState)
graph.add_node('validate_purity', validate_buffer_purity)
graph.add_node('check_temp', verify_storage_requirements)
graph.add_edge('validate_purity', 'check_temp')
graph.add_edge('check_temp', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()
