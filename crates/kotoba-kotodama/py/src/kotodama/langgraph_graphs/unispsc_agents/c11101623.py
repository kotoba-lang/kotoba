from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_spec: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_catalyst_purity(state: CatalystState) -> CatalystState:
    spec = state.get('material_spec', {})
    purity = spec.get('purity', 0)
    if purity >= 99.9:
        return {'validation_logs': ['Purity check passed: >99.9%'], 'is_approved': True}
    return {'validation_logs': ['Purity check failed: Below 99.9%'], 'is_approved': False}

def check_msds(state: CatalystState) -> CatalystState:
    if state.get('material_spec', {}).get('msds_attached', False):
        return {'validation_logs': ['MSDS documentation attached'], 'is_approved': state.get('is_approved', False)}
    return {'validation_logs': ['MSDS missing'], 'is_approved': False}

graph = StateGraph(CatalystState)
graph.add_node('validate_purity', validate_catalyst_purity)
graph.add_node('validate_msds', check_msds)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'validate_msds')
graph.add_edge('validate_msds', END)
graph = graph.compile()
