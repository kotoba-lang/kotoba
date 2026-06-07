from typing import TypedDict
from langgraph.graph import StateGraph, END

class ArtMaterialState(TypedDict):
    paper_specs: dict
    compliance_verified: bool

def validate_specs(state: ArtMaterialState):
    # Business logic for confirming paper weight and non-toxicity
    specs = state.get('paper_specs', {})
    is_safe = specs.get('non_toxic', False) and specs.get('gsm', 0) > 100
    return {'compliance_verified': is_safe}

def finalize_procurement(state: ArtMaterialState):
    if state['compliance_verified']:
        print('Procurement authorized for finger paint paper.')
    return {}

graph = StateGraph(ArtMaterialState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
