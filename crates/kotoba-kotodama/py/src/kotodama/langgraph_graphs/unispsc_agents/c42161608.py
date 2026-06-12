from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DialysateState(TypedDict):
    batch_number: str
    purity_certified: bool
    sterility_report: str
    inspection_passed: bool

def validate_batch(state: DialysateState):
    return {'inspection_passed': bool(state.get('batch_number') and state.get('purity_certified'))}

def check_sterility(state: DialysateState):
    report = state.get('sterility_report', '')
    return {'inspection_passed': 'sterile' in report.lower()}

graph = StateGraph(DialysateState)
graph.add_node('validate', validate_batch)
graph.add_node('sterility', check_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()
