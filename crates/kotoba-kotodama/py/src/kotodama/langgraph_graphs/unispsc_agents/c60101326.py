from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PhonicsState(TypedDict):
    card_content: str
    compliance_check: bool
    approved: bool

def validate_curriculum(state: PhonicsState):
    # Business logic for phonics standards validation
    state['compliance_check'] = 'phonics_standard' in state.get('card_content', '').lower()
    return state

def approval_step(state: PhonicsState):
    state['approved'] = state.get('compliance_check', False)
    return state

graph = StateGraph(PhonicsState)
graph.add_node('validate', validate_curriculum)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
