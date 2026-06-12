from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class AnimalFeedState(TypedDict):
    batch_id: str
    material_spec: Dict[str, Any]
    quality_status: str
    risk_assessment: List[str]
    approved: bool

def validate_materials(state: AnimalFeedState) -> AnimalFeedState:
    spec = state.get('material_spec', {})
    if spec.get('purity_index', 0) > 0.95:
        state['quality_status'] = 'PASSED'
    else:
        state['quality_status'] = 'REJECTED'
    return state

def check_compliance(state: AnimalFeedState) -> AnimalFeedState:
    if state['quality_status'] == 'PASSED':
        state['approved'] = True
    else:
        state['approved'] = False
    return state

builder = StateGraph(AnimalFeedState)
builder.add_node('validate', validate_materials)
builder.add_node('compliance', check_compliance)
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
builder.set_entry_point('validate')
graph = builder.compile()
