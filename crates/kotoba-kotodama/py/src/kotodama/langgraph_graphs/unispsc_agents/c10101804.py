from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    commodity_id: str
    species: str
    validation_checks: List[str]
    is_approved: bool

def validate_breeding_criteria(state: LivestockState):
    checks = state.get('validation_checks', [])
    if state.get('species') == 'Unknown':
        checks.append('SPECIES_MISSING')
    else:
        checks.append('SPECIES_VALIDATED')
    return {'validation_checks': checks}

def approval_node(state: LivestockState):
    is_approved = 'SPECIES_VALIDATED' in state.get('validation_checks', [])
    return {'is_approved': is_approved}

builder = StateGraph(LivestockState)
builder.add_node('validate', validate_breeding_criteria)
builder.add_node('approve', approval_node)
builder.set_entry_point('validate')
builder.add_edge('validate', 'approve')
builder.add_edge('approve', END)
graph = builder.compile()
