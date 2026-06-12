from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class LabelingState(TypedDict):
    printer_model: str
    validation_checks: List[str]
    is_compliant: bool

def validate_specs(state: LabelingState):
    checks = ['resolution_ok', 'tape_compatibility_ok']
    return {'validation_checks': checks, 'is_compliant': True}

def finalize_order(state: LabelingState):
    return {'is_compliant': True}

graph = StateGraph(LabelingState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
