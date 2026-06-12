from langgraph.graph import StateGraph, END
from typing import TypedDict
class CrackersState(TypedDict):
    batch_id: str
    quality_check_passed: bool
    is_expired: bool
def validate_expiry(state: CrackersState):
    state['is_expired'] = False # Placeholder logic
    return state
def check_quality(state: CrackersState):
    state['quality_check_passed'] = True # Placeholder for visual/lab inspection
    return state
graph = StateGraph(CrackersState)
graph.add_node('validate_expiry', validate_expiry)
graph.add_node('quality_check', check_quality)
graph.set_entry_point('validate_expiry')
graph.add_edge('validate_expiry', 'quality_check')
graph.add_edge('quality_check', END)
graph = graph.compile()
