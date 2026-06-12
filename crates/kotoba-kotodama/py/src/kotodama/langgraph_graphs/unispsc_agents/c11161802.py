from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AluminumProcurementState(TypedDict):
    material_id: str
    purity_check: bool
    physical_test_results: dict
    approved: bool

def validate_material_purity(state: AluminumProcurementState) -> AluminumProcurementState:
    # Simulate stringent purity validation logic for UNSPSC 11161802
    state['purity_check'] = True
    return state

def run_physical_tests(state: AluminumProcurementState) -> AluminumProcurementState:
    # Simulate CAD/Engineering stress tests
    state['physical_test_results'] = {'tensile_pass': True, 'hardness_pass': True}
    state['approved'] = True
    return state

builder = StateGraph(AluminumProcurementState)
builder.add_node('validate_purity', validate_material_purity)
builder.add_node('physical_tests', run_physical_tests)
builder.set_entry_point('validate_purity')
builder.add_edge('validate_purity', 'physical_tests')
builder.add_edge('physical_tests', END)
graph = builder.compile()
