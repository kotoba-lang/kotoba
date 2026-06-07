from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class OfficeSupplyState(TypedDict):
    item_code: str
    batch_id: str
    quality_checks: List[str]
    is_approved: bool

def validate_clip_quality(state: OfficeSupplyState):
    checks = state.get('quality_checks', [])
    if 'tensile_strength_pass' in checks and 'coating_integrity_pass' in checks:
        return {'is_approved': True}
    return {'is_approved': False}

def update_procurement_state(state: OfficeSupplyState):
    return {'is_approved': state['is_approved']}

graph = StateGraph(OfficeSupplyState)
graph.add_node('validate', validate_clip_quality)
graph.add_node('update', update_procurement_state)
graph.set_entry_point('validate')
graph.add_edge('validate', 'update')
graph.add_edge('update', END)
graph = graph.compile()
