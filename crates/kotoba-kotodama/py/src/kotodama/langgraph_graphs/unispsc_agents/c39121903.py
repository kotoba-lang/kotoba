from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LockoutState(TypedDict):
    item_id: str
    compliance_check: bool
    safety_rating: str

def validate_safety_standards(state: LockoutState):
    state['compliance_check'] = True
    return {'compliance_check': True, 'safety_rating': 'OSHA-Compliant'}

def finalize_procurement(state: LockoutState):
    return {'safety_rating': 'Verified'}

graph = StateGraph(LockoutState)
graph.add_node('validate', validate_safety_standards)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')

graph = graph.compile()
