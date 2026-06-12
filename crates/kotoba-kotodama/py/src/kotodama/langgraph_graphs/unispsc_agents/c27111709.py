from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_id: str
    material_certified: bool
    hardness_check_passed: bool

def validate_material(state: ToolState) -> ToolState:
    state['material_certified'] = True
    return state

def validate_hardness(state: ToolState) -> ToolState:
    state['hardness_check_passed'] = True
    return state

graph = StateGraph(ToolState)
graph.add_node('validate_material', validate_material)
graph.add_node('validate_hardness', validate_hardness)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'validate_hardness')
graph.add_edge('validate_hardness', END)
graph = graph.compile()
