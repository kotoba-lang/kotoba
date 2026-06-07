from typing import TypedDict
from langgraph.graph import StateGraph, END

class AccordionState(TypedDict):
    model_id: str
    tuning_verified: bool
    physical_inspection: bool

def verify_tuning(state: AccordionState):
    state['tuning_verified'] = True
    return state

def perform_physical_check(state: AccordionState):
    state['physical_inspection'] = True
    return state

graph = StateGraph(AccordionState)
graph.add_node('verify_tuning', verify_tuning)
graph.add_node('physical_check', perform_physical_check)
graph.set_entry_point('verify_tuning')
graph.add_edge('verify_tuning', 'physical_check')
graph.add_edge('physical_check', END)
graph = graph.compile()
