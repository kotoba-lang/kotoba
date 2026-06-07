from langgraph.graph import StateGraph, END
from typing import TypedDict

class SousaphoneState(TypedDict):
    spec_received: bool
    qc_passed: bool

def validate_specs(state: SousaphoneState):
    print('Validating musical acoustic specifications...')
    return {'spec_received': True}

def perform_qc(state: SousaphoneState):
    print('Performing mechanical valve and intonation inspection...')
    return {'qc_passed': True}

graph = StateGraph(SousaphoneState)
graph.add_node('validate', validate_specs)
graph.add_node('qc', perform_qc)
graph.set_entry_point('validate')
graph.add_edge('validate', 'qc')
graph.add_edge('qc', END)
graph = graph.compile()
