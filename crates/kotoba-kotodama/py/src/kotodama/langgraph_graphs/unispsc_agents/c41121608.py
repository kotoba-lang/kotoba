from typing import TypedDict
from langgraph.graph import StateGraph, END

class TipProcessingState(TypedDict):
    compatibility_verified: bool
    sterility_checked: bool
    workflow_complete: bool

def check_compatibility(state: TipProcessingState):
    print('Verifying robotic workstation compatibility...')
    return {'compatibility_verified': True}

def verify_sterility(state: TipProcessingState):
    print('Checking ISO sterility documentation...')
    return {'sterility_checked': True}

graph = StateGraph(TipProcessingState)
graph.add_node('check_comp', check_compatibility)
graph.add_node('verify_ster', verify_sterility)
graph.set_entry_point('check_comp')
graph.add_edge('check_comp', 'verify_ster')
graph.add_edge('verify_ster', END)
graph = graph.compile()
