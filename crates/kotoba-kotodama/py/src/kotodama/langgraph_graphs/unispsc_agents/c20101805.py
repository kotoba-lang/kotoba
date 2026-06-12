from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class GearProcurementState(TypedDict):
    gear_specs: dict
    validation_logs: Annotated[List[str], add_messages]
    approved: bool

def validate_gear_specs(state: GearProcurementState) -> GearProcurementState:
    specs = state.get('gear_specs', {})
    if 'precision_tolerance' in specs and specs['precision_tolerance'] < 0.001:
        state['validation_logs'].append('High precision validation passed.')
        state['approved'] = True
    else:
        state['validation_logs'].append('Precision tolerance check failed.')
        state['approved'] = False
    return state

def route_by_approval(state: GearProcurementState) -> str:
    return 'approved' if state.get('approved') else 'manual_review'

graph = StateGraph(GearProcurementState)
graph.add_node('validator', validate_gear_specs)
graph.set_entry_point('validator')
graph.add_conditional_edges('validator', route_by_approval, {'approved': END, 'manual_review': END})

graph = graph.compile()
