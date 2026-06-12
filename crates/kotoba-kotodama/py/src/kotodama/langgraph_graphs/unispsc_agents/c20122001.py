from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
import operator

class ControlState(TypedDict):
    part_id: str
    specs: Dict[str, Any]
    validation_results: Annotated[List[str], operator.add]
    is_approved: bool

def validate_load_specs(state: ControlState) -> ControlState:
    specs = state.get('specs', {})
    if specs.get('load_capacity_rating', 0) > 0:
        state['validation_results'].append('Load specs validated.')
    else:
        state['validation_results'].append('Load specs invalid.')
    return state

def approve_component(state: ControlState) -> ControlState:
    if 'Load specs validated.' in state['validation_results']:
        state['is_approved'] = True
    return state

# Compile Graph
builder = StateGraph(ControlState)
builder.add_node('validate', validate_load_specs)
builder.add_node('approve', approve_component)
builder.add_edge('validate', 'approve')
builder.add_edge('approve', END)
builder.set_entry_point('validate')
graph = builder.compile()
