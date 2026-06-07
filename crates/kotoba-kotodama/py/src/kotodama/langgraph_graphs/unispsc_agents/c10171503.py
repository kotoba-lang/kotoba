from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SeedlingState(TypedDict):
    seed_batch_id: str
    purity_check: bool
    quarantine_status: bool
    is_approved: bool

def validate_seed_purity(state: SeedlingState) -> dict:
    # Specialized validation logic for seed purity
    return {'purity_check': True}

def verify_quarantine(state: SeedlingState) -> dict:
    # Workflow step for checking international/domestic quarantine status
    return {'quarantine_status': True}

def approve_procurement(state: SeedlingState) -> dict:
    # Final decision node
    return {'is_approved': state['purity_check'] and state['quarantine_status']}

graph = StateGraph(SeedlingState)
graph.add_node('validate_purity', validate_seed_purity)
graph.add_node('verify_quarantine', verify_quarantine)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_quarantine')
graph.add_edge('verify_quarantine', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
