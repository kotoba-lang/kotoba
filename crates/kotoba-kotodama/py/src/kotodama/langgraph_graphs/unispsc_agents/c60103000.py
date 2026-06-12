from typing import TypedDict
from langgraph.graph import StateGraph, END

class EduToolState(TypedDict):
    item_name: str
    safety_check_passed: bool
    curriculum_compliance: bool

def validate_materials(state: EduToolState) -> EduToolState:
    state['safety_check_passed'] = True
    return state

def check_curriculum_match(state: EduToolState) -> EduToolState:
    state['curriculum_compliance'] = True
    return state

graph = StateGraph(EduToolState)
graph.add_node('validate_safety', validate_materials)
graph.add_node('match_curriculum', check_curriculum_match)
graph.set_entry_point('validate_safety')
graph.add_edge('validate_safety', 'match_curriculum')
graph.add_edge('match_curriculum', END)
graph = graph.compile()
