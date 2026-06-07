from typing import TypedDict
from langgraph.graph import StateGraph

class RFSpecState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_rf_specs(state: RFSpecState):
    specs = state.get('spec_data', {})
    # Logic to check bandwidth logic or insertion loss limits
    is_valid = all(key in specs for key in ['center_frequency_mhz', 'insertion_loss_db'])
    return {'validation_result': is_valid}

builder = StateGraph(RFSpecState)
builder.add_node('validator', validate_rf_specs)
builder.set_entry_point('validator')
builder.set_finish_point('validator')
graph = builder.compile()
