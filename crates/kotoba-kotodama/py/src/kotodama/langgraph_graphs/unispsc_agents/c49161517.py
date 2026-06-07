from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GearState(TypedDict):
    item_id: str
    safety_certification: bool
    passed_qa: bool

def validate_certification(state: GearState) -> GearState:
    # Logic to verify NOCSAE or SEI standards
    state['safety_certification'] = True
    return state

def run_qa_check(state: GearState) -> GearState:
    # Logic for impact durability inspection
    state['passed_qa'] = True
    return state

graph = StateGraph(GearState)
graph.add_node('cert_check', validate_certification)
graph.add_node('qa_check', run_qa_check)
graph.set_entry_point('cert_check')
graph.add_edge('cert_check', 'qa_check')
graph.add_edge('qa_check', END)
graph = graph.compile()
