from typing import TypedDict
from langgraph.graph import StateGraph, END

class OrthoState(TypedDict):
    material_certified: bool
    sterilization_verified: bool
    batch_number: str

def check_compliance(state: OrthoState):
    print('Verifying ISO 13485 compliance...')
    return {'material_certified': True}

def validate_batch(state: OrthoState):
    print(f'Validating batch: {state.get('batch_number')}')
    return {'sterilization_verified': True}

graph = StateGraph(OrthoState)
graph.add_node('check_compliance', check_compliance)
graph.add_node('validate_batch', validate_batch)
graph.set_entry_point('check_compliance')
graph.add_edge('check_compliance', 'validate_batch')
graph.add_edge('validate_batch', END)
graph = graph.compile()
