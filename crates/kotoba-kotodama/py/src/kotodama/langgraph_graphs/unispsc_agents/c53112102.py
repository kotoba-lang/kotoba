from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OvershoeState(TypedDict):
    specifications: dict
    validation_passed: bool
    errors: List[str]

def validate_overshoe_specs(state: OvershoeState):
    specs = state.get('specifications', {})
    errors = []
    if not specs.get('waterproof'): errors.append('Missing waterproof rating')
    if not specs.get('material'): errors.append('Missing material specification')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

workflow = StateGraph(OvershoeState)
workflow.add_node('validate', validate_overshoe_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
