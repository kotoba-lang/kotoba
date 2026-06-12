from typing import TypedDict
from langgraph.graph import StateGraph, END

class MugsState(TypedDict):
    material_compliance: bool
    safety_tests_passed: bool
    quality_status: str

def validate_materials(state: MugsState):
    state['material_compliance'] = True
    return state

def run_safety_checks(state: MugsState):
    state['safety_tests_passed'] = True
    state['quality_status'] = 'verified'
    return state

graph = StateGraph(MugsState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('run_safety_checks', run_safety_checks)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'run_safety_checks')
graph.add_edge('run_safety_checks', END)

graph = graph.compile()
