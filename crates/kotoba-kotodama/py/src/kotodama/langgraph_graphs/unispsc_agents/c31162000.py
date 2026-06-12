from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class NailProcurementState(TypedDict):
    material: str
    spec_compliant: bool
    inspection_result: dict

def validate_specs(state: NailProcurementState):
    state['spec_compliant'] = state.get('material') is not None
    return state

def run_inspection(state: NailProcurementState):
    state['inspection_result'] = {'status': 'pass' if state['spec_compliant'] else 'fail'}
    return state

graph = StateGraph(NailProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('inspect', run_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
