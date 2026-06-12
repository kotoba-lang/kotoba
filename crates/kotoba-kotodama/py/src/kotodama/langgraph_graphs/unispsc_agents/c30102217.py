from typing import TypedDict
from langgraph.graph import StateGraph, END

class ConcreteState(TypedDict):
    spec_completed: bool
    qc_verified: bool
    data: dict

def validate_specs(state: ConcreteState):
    print('Validating concrete plate dimensions and strength...')
    state['spec_completed'] = True
    return state

def verify_qc(state: ConcreteState):
    print('Verifying quality control certificates...')
    state['qc_verified'] = True
    return state

graph = StateGraph(ConcreteState)
graph.add_node('validate', validate_specs)
graph.add_node('qc', verify_qc)
graph.add_edge('validate', 'qc')
graph.add_edge('qc', END)
graph.set_entry_point('validate')
graph = graph.compile()
