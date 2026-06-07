from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    spec_compliance: bool
    sterilization_validated: bool
    quality_score: int

def validate_material(state: ProcessingState):
    state['spec_compliance'] = True
    return state

def check_sterilization_records(state: ProcessingState):
    state['sterilization_validated'] = True
    return state

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_material)
graph.add_node('check', check_sterilization_records)
graph.add_edge('validate', 'check')
graph.add_edge('check', END)
graph.set_entry_point('validate')
graph = graph.compile()
