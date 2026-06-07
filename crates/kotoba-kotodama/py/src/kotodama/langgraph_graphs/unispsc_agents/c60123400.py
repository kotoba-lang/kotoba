from langgraph.graph import StateGraph, END
from typing import TypedDict
class MaterialState(TypedDict):
    material_name: str
    safety_compliant: bool
    inspection_passed: bool
def validate_materials(state: MaterialState):
    state['safety_compliant'] = True
    return state
def run_inspection(state: MaterialState):
    state['inspection_passed'] = True
    return state
graph = StateGraph(MaterialState)
graph.add_node('validate', validate_materials)
graph.add_node('inspect', run_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
