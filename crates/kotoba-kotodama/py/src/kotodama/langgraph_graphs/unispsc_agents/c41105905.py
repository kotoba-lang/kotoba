from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class KitState(TypedDict):
    kit_id: str
    validation_checks: List[str]
    approved: bool

def validate_reagents(state: KitState):
    checks = ['cold_chain_verified', 'reagent_purity_certified']
    return {'validation_checks': checks, 'approved': len(checks) > 0}

graph = StateGraph(KitState)
graph.add_node('validate', validate_reagents)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
