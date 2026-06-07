from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    part_id: str
    material_certified: bool
    dimensional_check: bool

def validate_casting(state: ProcessingState):
    state['material_certified'] = True
    return state

def run_cnc_verification(state: ProcessingState):
    state['dimensional_check'] = True
    return state

graph = StateGraph(ProcessingState)
graph.add_node('validate_material', validate_casting)
graph.add_node('cnc_check', run_cnc_verification)
graph.add_edge('validate_material', 'cnc_check')
graph.add_edge('cnc_check', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
