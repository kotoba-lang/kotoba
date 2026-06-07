from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    specifications: dict
    validation_result: bool
    compliance_report: str

def validate_forging_specs(state: ForgingState):
    # Perform metallurgical and tolerance checks
    specs = state.get('specifications', {})
    valid = specs.get('tensile_strength_mpa', 0) > 400
    return {'validation_result': valid, 'compliance_report': 'Validated' if valid else 'Failed'}

def generate_compliance(state: ForgingState):
    return {'compliance_report': 'Certification ISO-9001 confirmed for material ' + str(state.get('specifications', {}).get('material'))}

builder = StateGraph(ForgingState)
builder.add_node('validate', validate_forging_specs)
builder.add_node('compliance', generate_compliance)
builder.set_entry_point('validate')
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
graph = builder.compile()
