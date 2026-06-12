from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SteamApplianceState(TypedDict):
    specs: dict
    validated: bool
    errors: List[str]

def validate_specs(state: SteamApplianceState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('voltage') not in [100, 110, 220]:
        errors.append('Invalid target voltage')
    if specs.get('tank_capacity', 0) <= 0:
        errors.append('Invalid tank capacity')
    return {'validated': len(errors) == 0, 'errors': errors}

workflow = StateGraph(SteamApplianceState)
workflow.add_node('validation', validate_specs)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
