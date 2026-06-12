from typing import TypedDict
from langgraph.graph import StateGraph, END

class CollatingRackState(TypedDict):
    spec_data: dict
    validation_status: bool
    error_log: list

def validate_rack_specs(state: CollatingRackState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('load_capacity_kg', 0) <= 0:
        errors.append('Invalid load capacity')
    return {'validation_status': len(errors) == 0, 'error_log': errors}

def finalize_procurement(state: CollatingRackState):
    print('Procurement request processed for collating racks')
    return {}

graph = StateGraph(CollatingRackState)
graph.add_node('validate', validate_rack_specs)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')

graph = graph.compile()
