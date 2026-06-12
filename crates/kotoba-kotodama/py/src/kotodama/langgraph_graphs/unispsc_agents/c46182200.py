from typing import TypedDict
from langgraph.graph import StateGraph, END

class ErgonomicState(TypedDict):
    product_id: str
    spec_data: dict
    validation_passed: bool

def validate_ergonomic_specs(state: ErgonomicState):
    # Simulate validation logic for ergonomic compliance
    specs = state.get('spec_data', {})
    is_valid = all(key in specs for key in ['load_capacity', 'iso_compliance'])
    print(f'Validating ergonomics: {is_valid}')
    return {'validation_passed': is_valid}

def trigger_procurement(state: ErgonomicState):
    print('Procurement workflow triggered for ergonomic aid.')
    return {}

builder = StateGraph(ErgonomicState)
builder.add_node('validate', validate_ergonomic_specs)
builder.add_node('procure', trigger_procurement)
builder.add_edge('validate', 'procure')
builder.add_edge('procure', END)
builder.set_entry_point('validate')
graph = builder.compile()
