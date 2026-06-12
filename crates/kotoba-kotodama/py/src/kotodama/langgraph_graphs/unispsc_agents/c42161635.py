from langgraph.graph import StateGraph, END
from typing import TypedDict

class DialysisState(TypedDict):
    cartridge_id: str
    is_sterile: bool
    clearance_passed: bool

def validate_sterility(state: DialysisState):
    return {'is_sterile': True}

def check_clearance(state: DialysisState):
    return {'clearance_passed': True}

graph = StateGraph(DialysisState)
graph.add_node('verify_sterile', validate_sterility)
graph.add_node('check_performance', check_clearance)
graph.set_entry_point('verify_sterile')
graph.add_edge('verify_sterile', 'check_performance')
graph.add_edge('check_performance', END)
graph = graph.compile()
