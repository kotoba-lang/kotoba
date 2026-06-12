from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_id: str
    material_compliance: bool
    safety_check_passed: bool

def validate_material(state: ToolState):
    state['material_compliance'] = True
    return state

def safety_inspection(state: ToolState):
    state['safety_check_passed'] = True
    return state

graph = StateGraph(ToolState)
graph.add_node('validate_material', validate_material)
graph.add_node('safety_inspection', safety_inspection)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'safety_inspection')
graph.add_edge('safety_inspection', END)
graph = graph.compile()
