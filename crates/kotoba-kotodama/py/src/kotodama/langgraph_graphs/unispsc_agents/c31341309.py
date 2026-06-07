from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    material_grade: str
    welding_check: bool
    dimensions_ok: bool

def validate_specs(state: AssemblyState):
    state['welding_check'] = state.get('material_grade') == 'SUS316'
    state['dimensions_ok'] = True
    return state

def check_quality(state: AssemblyState):
    return 'pass' if state['welding_check'] and state['dimensions_ok'] else 'fail'

graph = StateGraph(AssemblyState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
