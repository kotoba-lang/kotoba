from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_id: str
    material_certified: bool
    torque_check_passed: bool

def validate_tool(state: ToolState):
    state['material_certified'] = True
    return state

def verify_torque(state: ToolState):
    state['torque_check_passed'] = True
    return state

graph = StateGraph(ToolState)
graph.add_node('validate', validate_tool)
graph.add_node('torque', verify_torque)
graph.set_entry_point('validate')
graph.add_edge('validate', 'torque')
graph.add_edge('torque', END)
graph = graph.compile()
