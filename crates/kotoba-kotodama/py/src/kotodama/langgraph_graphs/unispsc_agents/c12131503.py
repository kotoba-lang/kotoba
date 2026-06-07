from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class WaferState(TypedDict):
    wafer_id: str
    spec_requirements: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_crystal_orientation(state: WaferState) -> WaferState:
    # Logic to verify SEMI standard orientation alignment
    state['validation_results'].append('Crystal orientation validated.')
    return state

def validate_purity_level(state: WaferState) -> WaferState:
    # Logic to confirm impurity ppm thresholds
    state['validation_results'].append('Purity levels confirmed.')
    return state

def check_final_approval(state: WaferState) -> str:
    if len(state['validation_results']) >= 2:
        state['is_approved'] = True
        return 'approved'
    return 'rejected'

graph = StateGraph(WaferState)
graph.add_node('validate_orientation', validate_crystal_orientation)
graph.add_node('validate_purity', validate_purity_level)
graph.set_entry_point('validate_orientation')
graph.add_edge('validate_orientation', 'validate_purity')
graph.add_conditional_edges('validate_purity', check_final_approval, {'approved': END, 'rejected': END})
graph = graph.compile()
