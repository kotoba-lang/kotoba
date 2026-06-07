from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolProcessState(TypedDict):
    tool_id: str
    material_compliance: bool
    inspection_passed: bool

def validate_material(state: ToolProcessState):
    state['material_compliance'] = True
    return state

def run_inspection(state: ToolProcessState):
    state['inspection_passed'] = True
    return state

graph = StateGraph(ToolProcessState)
graph.add_node('validate', validate_material)
graph.add_node('inspect', run_inspection)
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph.set_entry_point('validate')
graph = graph.compile()
