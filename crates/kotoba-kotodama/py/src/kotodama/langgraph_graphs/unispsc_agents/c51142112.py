from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    purity_check: bool
    compliant: bool

def validate_quality(state: PharmState):
    state['purity_check'] = True
    return {'purity_check': True}

def check_compliance(state: PharmState):
    state['compliant'] = state['purity_check']
    return {'compliant': state['compliant']}

graph = StateGraph(PharmState)
graph.add_node('validate', validate_quality)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
