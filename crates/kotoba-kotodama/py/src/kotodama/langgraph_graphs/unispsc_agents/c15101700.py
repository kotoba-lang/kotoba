from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

class FluidState(TypedDict):
    part_id: str
    specs: dict
    validation_logs: Annotated[List[str], operator.add]
    is_approved: bool

def validate_specs(state: FluidState) -> FluidState:
    specs = state.get('specs', {})
    if 'pressure_rating_mpa' in specs:
        state['validation_logs'] = [f'Verified pressure rating: {specs['pressure_rating_mpa']} MPa']
        state['is_approved'] = True
    else:
        state['validation_logs'] = ['Missing critical pressure specifications']
        state['is_approved'] = False
    return state

def process_logistics(state: FluidState) -> FluidState:
    state['validation_logs'].append('Logistics compliance check passed.')
    return state

graph = StateGraph(FluidState)
graph.add_node('validate', validate_specs)
graph.add_node('logistics', process_logistics)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('validate')
graph = graph.compile()
