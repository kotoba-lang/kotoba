from typing import TypedDict, List, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GasProcurementState(TypedDict):
    commodity_id: str
    composition: dict
    safety_check_passed: bool
    log: Annotated[List[str], operator.add]

def validate_composition(state: GasProcurementState) -> dict:
    composition = state.get('composition', {})
    is_valid = all(v > 0 for v in composition.values())
    return {'safety_check_passed': is_valid, 'log': ['Composition validated.']}

def route_by_safety(state: GasProcurementState) -> str:
    return 'VALID' if state['safety_check_passed'] else 'FAIL'

def log_failure(state: GasProcurementState) -> dict:
    return {'log': ['Safety check failed, triggering hazardous material review.']}

graph = StateGraph(GasProcurementState)
graph.add_node('validate', validate_composition)
graph.add_node('fail_handler', log_failure)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_safety, {'VALID': END, 'FAIL': 'fail_handler'})
graph.add_edge('fail_handler', END)
graph = graph.compile()
