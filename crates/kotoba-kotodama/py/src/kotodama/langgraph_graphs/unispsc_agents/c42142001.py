from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_id: str
    material_certified: bool
    sterility_confirmed: bool
    is_approved: bool

def check_material(state: ToolState):
    state['material_certified'] = True
    return state

def validate_sterility(state: ToolState):
    state['sterility_confirmed'] = True
    return state

def finalize_approval(state: ToolState):
    state['is_approved'] = state['material_certified'] and state['sterility_confirmed']
    return state

graph = StateGraph(ToolState)
graph.add_node('check_material', check_material)
graph.add_node('validate_sterility', validate_sterility)
graph.add_node('finalize', finalize_approval)

graph.add_edge('check_material', 'validate_sterility')
graph.add_edge('validate_sterility', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('check_material')
graph = graph.compile()
