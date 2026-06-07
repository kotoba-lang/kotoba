from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ShieldingGloveState(TypedDict):
    lead_equiv: float
    certification_check: bool
    is_approved: bool

def validate_shielding(state: ShieldingGloveState):
    # Minimum 0.25mm lead equivalent required for clinical standard
    if state.get('lead_equiv', 0) >= 0.25:
        return {'certification_check': True, 'is_approved': True}
    return {'certification_check': False, 'is_approved': False}

def finalize_procurement(state: ShieldingGloveState):
    print('Procurement finalized for qualified shielding equipment.')
    return {}

graph = StateGraph(ShieldingGloveState)
graph.add_node('validate', validate_shielding)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
