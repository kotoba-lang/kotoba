from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class PowerTransmissionState(TypedDict):
    part_id: str
    specs: dict
    validation_log: List[str]
    is_approved: bool

def validate_specs(state: PowerTransmissionState) -> dict:
    specs = state.get('specs', {})
    log = []
    if specs.get('load_capacity', 0) < 10:
        log.append('Load capacity below industrial safety threshold')
    return {'validation_log': log}

def approval_check(state: PowerTransmissionState) -> str:
    if not state.get('validation_log'):
        return 'approved'
    return 'flagged'

workflow = StateGraph(PowerTransmissionState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_conditional_edges('validate', approval_check, {'approved': END, 'flagged': END})
graph = workflow.compile()
