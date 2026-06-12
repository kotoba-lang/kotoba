from typing import TypedDict
from langgraph.graph import StateGraph, END

class ClothingState(TypedDict):
    spec_content: dict
    validated: bool

def validate_textile_specs(state: ClothingState):
    # Business logic for textile compliance check
    specs = state.get('spec_content', {})
    is_valid = all(k in specs for k in ['material', 'safety_cert'])
    print(f'Validating specs: {is_valid}')
    return {'validated': is_valid}

workflow = StateGraph(ClothingState)
workflow.add_node('compliance_checker', validate_textile_specs)
workflow.set_entry_point('compliance_checker')
workflow.add_edge('compliance_checker', END)

graph = workflow.compile()
