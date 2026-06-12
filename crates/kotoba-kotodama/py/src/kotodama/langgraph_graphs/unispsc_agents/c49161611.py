from typing import TypedDict
from langgraph.graph import StateGraph, END

class TennisAidState(TypedDict):
    item_name: str
    spec_verified: bool
    safety_check: bool

def validate_equipment(state: TennisAidState) -> TennisAidState:
    state['spec_verified'] = True
    return state

def safety_inspection(state: TennisAidState) -> TennisAidState:
    state['safety_check'] = True
    return state

graph = StateGraph(TennisAidState)
graph.add_node('validate', validate_equipment)
graph.add_node('safety', safety_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
