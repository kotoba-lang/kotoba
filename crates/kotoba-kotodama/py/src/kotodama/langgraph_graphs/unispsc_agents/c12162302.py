from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    processed_data: list

def validate_purity(state: CatalystState) -> CatalystState:
    # Logic to verify chemical purity specs
    state['purity_check'] = True
    return state

def verify_safety(state: CatalystState) -> CatalystState:
    # Logic for hazardous material handling and export control compliance
    state['safety_clearance'] = True
    return state

def aggregate_results(state: CatalystState) -> CatalystState:
    state['processed_data'] = ['purity_verified', 'safety_approved']
    return state

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_purity)
graph.add_node('safety', verify_safety)
graph.add_node('finish', aggregate_results)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', 'finish')
graph.add_edge('finish', END)
graph.set_entry_point('validate')
graph = graph.compile()
