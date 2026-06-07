from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    material_id: str
    purity_check: bool
    safety_compliance: bool
    cold_chain_verified: bool
    is_approved: bool

def validate_purity(state: ReagentState):
    # Business logic for CAS and Purity verification
    return {'purity_check': True}

def verify_safety(state: ReagentState):
    # Logic to check SDS compliance for hazardous reagents
    return {'safety_compliance': True}

def finalize_procurement(state: ReagentState):
    # Approve if all checks pass
    is_ok = state['purity_check'] and state['safety_compliance']
    return {'is_approved': is_ok}

graph = StateGraph(ReagentState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_safety', verify_safety)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_safety')
graph.add_edge('verify_safety', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
