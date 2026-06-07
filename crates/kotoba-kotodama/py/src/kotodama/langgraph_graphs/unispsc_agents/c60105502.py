from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MaterialState(TypedDict):
    material_id: str
    safety_check_passed: bool
    media_type: str
    curriculum_ready: bool

def validate_materials(state: MaterialState):
    return {'safety_check_passed': True}

def process_curriculum(state: MaterialState):
    return {'curriculum_ready': True}

graph = StateGraph(MaterialState)
graph.add_node('safety', validate_materials)
graph.add_node('curriculum', process_curriculum)
graph.set_entry_point('safety')
graph.add_edge('safety', 'curriculum')
graph.add_edge('curriculum', END)
graph = graph.compile()
