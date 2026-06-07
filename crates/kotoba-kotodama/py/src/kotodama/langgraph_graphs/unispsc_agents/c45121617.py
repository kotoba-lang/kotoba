from typing import TypedDict
from langgraph.graph import StateGraph, END

class CameraBagState(TypedDict):
    bag_specs: dict
    validation_report: dict

def validate_specs(state: CameraBagState):
    specs = state.get('bag_specs', {})
    is_valid = 'shock_absorption' in specs and 'waterproof_rating' in specs
    return {'validation_report': {'passed': is_valid}}

def finalize_order(state: CameraBagState):
    return {'validation_report': {'status': 'approved'}}

graph = StateGraph(CameraBagState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', finalize_order)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
