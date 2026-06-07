from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SmeltingState(TypedDict):
    batch_id: str
    material_spec: dict
    validation_log: List[str]
    is_approved: bool

def validate_flux_specs(state: SmeltingState) -> SmeltingState:
    spec = state.get('material_spec', {})
    log = state.get('validation_log', [])
    if spec.get('purity', 0) >= 98.0:
        log.append('Purity check passed')
        state['is_approved'] = True
    else:
        log.append('Purity check failed')
        state['is_approved'] = False
    state['validation_log'] = log
    return state

def route_by_approval(state: SmeltingState) -> str:
    return 'approved' if state['is_approved'] else 'rejected'

builder = StateGraph(SmeltingState)
builder.add_node('validate', validate_flux_specs)
builder.set_entry_point('validate')
builder.add_conditional_edges('validate', route_by_approval, {'approved': END, 'rejected': END})
graph = builder.compile()
