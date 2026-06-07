from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AgaroseState(TypedDict):
    batch_id: str
    purity_check: bool
    gel_strength_kpa: float
    status: str

def validate_agarose_purity(state: AgaroseState):
    # Simulate high-purity validation logic
    is_pure = state.get('purity_check', False)
    return {'status': 'validated' if is_pure else 'rejected'}

def check_physical_specs(state: AgaroseState):
    strength = state.get('gel_strength_kpa', 0)
    return {'status': 'spec_approved' if strength > 1200 else 'spec_failed'}

graph = StateGraph(AgaroseState)
graph.add_node('purity', validate_agarose_purity)
graph.add_node('specs', check_physical_specs)
graph.set_entry_point('purity')
graph.add_edge('purity', 'specs')
graph.add_edge('specs', END)
graph = graph.compile()
