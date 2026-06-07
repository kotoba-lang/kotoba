from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EsmololState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_cleared: bool

def validate_batch(state: EsmololState):
    state['purity_check'] = True
    return state

def check_compliance(state: EsmololState):
    state['compliance_cleared'] = True
    return state

graph = StateGraph(EsmololState)
graph.add_node('validate_batch', validate_batch)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_batch')
graph.add_edge('validate_batch', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()
