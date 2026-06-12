from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    spec_requirements: dict
    is_validated: bool

def validate_specs(state: ProcurementState):
    specs = state.get('spec_requirements', {})
    is_valid = 'denier' in specs and 'composition' in specs
    return {'is_validated': is_valid}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
