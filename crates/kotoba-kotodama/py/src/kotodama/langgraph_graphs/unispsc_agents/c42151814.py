from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    adapter_spec: dict
    validation_result: bool

def validate_specs(state: DentalState):
    spec = state.get('adapter_spec', {})
    is_valid = all(k in spec for k in ['material', 'tolerance', 'iso_cert'])
    print(f'Validating dental chuck specs: {is_valid}')
    return {'validation_result': is_valid}

def process_procurement(state: DentalState):
    print('Proceeding with medical procurement workflow.')
    return {'validation_result': True}

graph = StateGraph(DentalState)
graph.add_node('validate', validate_specs)
graph.add_node('procure', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph = graph.compile()
