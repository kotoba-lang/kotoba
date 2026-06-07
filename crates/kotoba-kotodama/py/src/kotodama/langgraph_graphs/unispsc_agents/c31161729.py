from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_specs: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: ProcurementState):
    specs = state.get('part_specs', {})
    required = ['material', 'thread_size', 'knurl_pattern']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'error_log': [] if passed else ['Missing required specs']}

def process_procurement(state: ProcurementState):
    return {'validation_passed': True}

workflow = StateGraph(ProcurementState)
workflow.add_node('validate', validate_specs)
workflow.add_node('process', process_procurement)
workflow.add_edge('validate', 'process')
workflow.add_edge('process', END)
workflow.set_entry_point('validate')
graph = workflow.compile()
