from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SurgicalToolState(TypedDict):
    tool_id: str
    material_certified: bool
    sterilization_validated: bool
    tolerance_checked: bool
    is_approved: bool

def validate_materials(state: SurgicalToolState):
    state['material_certified'] = True
    return state

def validate_specs(state: SurgicalToolState):
    state['tolerance_checked'] = True
    return state

def final_check(state: SurgicalToolState):
    state['is_approved'] = state['material_certified'] and state['tolerance_checked']
    return state

graph = StateGraph(SurgicalToolState)
graph.add_node('material', validate_materials)
graph.add_node('specs', validate_specs)
graph.add_node('approval', final_check)

graph.set_entry_point('material')
graph.add_edge('material', 'specs')
graph.add_edge('specs', 'approval')
graph.add_edge('approval', END)
graph = graph.compile()
