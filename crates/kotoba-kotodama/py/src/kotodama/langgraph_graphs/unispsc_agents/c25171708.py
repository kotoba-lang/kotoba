from typing import TypedDict
from langgraph.graph import StateGraph, END

class BrakeState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_materials(state: BrakeState):
    pass

def check_tolerances(state: BrakeState):
    pass

def build_graph():
    graph = StateGraph(BrakeState)
    graph.add_node('validate_materials', validate_materials)
    graph.add_node('check_tolerances', check_tolerances)
    graph.set_entry_point('validate_materials')
    graph.add_edge('validate_materials', 'check_tolerances')
    graph.add_edge('check_tolerances', END)
    return graph.compile()

graph = build_graph()
