from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class CatalystState(TypedDict):
    composition: str
    purity: float
    status: str

def validate_composition(state: CatalystState) -> dict:
    # Logic to verify catalyst composition against safety standards
    if 'hazardous' in state['composition'].lower():
        return {'status': 'FLAGGED_FOR_SAFETY_REVIEW'}
    return {'status': 'VALIDATED'}

def route_by_purity(state: CatalystState) -> str:
    if state['purity'] < 0.99:
        return 'REJECT'
    return 'APPROVE'

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_composition)
graph.add_edge('validate', 'route')
graph.add_conditional_edges('route', route_by_purity, {'APPROVE': END, 'REJECT': END})
graph.set_entry_point('validate')

graph = graph.compile()
