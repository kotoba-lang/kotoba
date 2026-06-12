from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    quality_passed: bool
    temp_check: bool
    residue_clear: bool

def check_temp(state: ProcurementState) -> dict:
    return {'temp_check': True}

def check_quality(state: ProcurementState) -> dict:
    return {'quality_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('temp_check', check_temp)
graph.add_node('quality_check', check_quality)
graph.add_edge('temp_check', 'quality_check')
graph.add_edge('quality_check', END)
graph.set_entry_point('temp_check')
graph = graph.compile()
