from typing import TypedDict
from langgraph.graph import StateGraph, END

class EmeryBoardState(TypedDict):
    grit: str
    batch_id: str
    quality_check_passed: bool

def validate_grit(state: EmeryBoardState):
    valid_grits = ['fine', 'medium', 'coarse']
    return {'quality_check_passed': state.get('grit') in valid_grits}

def finalize_order(state: EmeryBoardState):
    return {'quality_check_passed': True}

graph = StateGraph(EmeryBoardState)
graph.add_node('validate', validate_grit)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
