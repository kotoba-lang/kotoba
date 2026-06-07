from typing import TypedDict
from langgraph.graph import StateGraph, END

class PaintState(TypedDict):
    spec_data: dict
    is_approved: bool

def validate_safety(state: PaintState):
    sds = state.get('spec_data', {}).get('sds_available', False)
    nontoxic = state.get('spec_data', {}).get('non_toxic_cert', False)
    return {'is_approved': sds and nontoxic}

def finalize_order(state: PaintState):
    return {'is_approved': True}

graph = StateGraph(PaintState)
graph.add_node('safety_check', validate_safety)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
