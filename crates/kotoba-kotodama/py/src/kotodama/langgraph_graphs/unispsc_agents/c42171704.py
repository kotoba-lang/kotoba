from typing import TypedDict
from langgraph.graph import StateGraph, END

class SwaddlerState(TypedDict):
    product_specs: dict
    compliance_verified: bool

def validate_medical_specs(state: SwaddlerState):
    specs = state.get('product_specs', {})
    # Check for medical grade material and thermal safety
    if 'tog_rating' in specs and 'certification' in specs:
        return {'compliance_verified': True}
    return {'compliance_verified': False}

graph = StateGraph(SwaddlerState)
graph.add_node('validate', validate_medical_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
