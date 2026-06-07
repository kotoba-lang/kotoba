from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class IrrigationState(TypedDict):
    specs: dict
    validated: bool
    error: List[str]

def validate_pump_specs(state: IrrigationState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('pressure', 0) < 0: errors.append('Invalid pressure')
    return {'validated': len(errors) == 0, 'error': errors}

workflow = StateGraph(IrrigationState)
workflow.add_node('validate', validate_pump_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
