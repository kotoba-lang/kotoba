from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SemiconductorState(TypedDict):
    material_id: str
    specifications: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_crystal_spec(state: SemiconductorState):
    specs = state.get('specifications', {})
    if specs.get('purity', 0) >= 99.999:
        return {'validation_log': ['Purity check passed'], 'is_approved': True}
    return {'validation_log': ['Insufficient purity'], 'is_approved': False}

def route_by_approval(state: SemiconductorState):
    return 'APPROVED' if state['is_approved'] else 'REJECTED'

graph = StateGraph(SemiconductorState)
graph.add_node('validate', validate_crystal_spec)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_approval, {'APPROVED': END, 'REJECTED': END})
graph = graph.compile()
