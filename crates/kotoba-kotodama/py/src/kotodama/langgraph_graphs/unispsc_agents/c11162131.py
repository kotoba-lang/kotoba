from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MagnesiumState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_validated: bool
    final_release: bool

def validate_purity(state: MagnesiumState):
    # Simulate spectroscopic analysis of magnesium purity
    return {'purity_check': True}

def check_export_controls(state: MagnesiumState):
    # Simulate dual-use regulatory screening
    return {'compliance_validated': True}

def finalize_batch(state: MagnesiumState):
    return {'final_release': True}

graph = StateGraph(MagnesiumState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_export_controls', check_export_controls)
graph.add_node('finalize_batch', finalize_batch)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_export_controls')
graph.add_edge('check_export_controls', 'finalize_batch')
graph.add_edge('finalize_batch', END)

graph = graph.compile()
