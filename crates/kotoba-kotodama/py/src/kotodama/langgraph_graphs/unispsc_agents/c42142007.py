from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolSpec(TypedDict):
    material_compliance: bool
    sterilization_test: bool
    inspection_passed: bool

def validate_materials(state: ToolSpec):
    state['material_compliance'] = True
    return state

def check_sterilization(state: ToolSpec):
    state['sterilization_test'] = True
    return state

def finalize_report(state: ToolSpec):
    state['inspection_passed'] = True
    return state

graph = StateGraph(ToolSpec)
graph.add_node('validate', validate_materials)
graph.add_node('sterilize', check_sterilization)
graph.add_node('finalize', finalize_report)
graph.add_edge('validate', 'sterilize')
graph.add_edge('sterilize', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
