from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DentalToolState(TypedDict):
    tool_id: str
    material: str
    sterilization_status: bool
    validation_errors: List[str]

def validate_specifications(state: DentalToolState):
    errors = []
    if state.get('material') != 'stainless_steel':
        errors.append('Invalid material: must be medical grade stainless steel.')
    if not state.get('sterilization_status'):
        errors.append('Instrument must be pre-sterilized.')
    return {'validation_errors': errors}

graph = StateGraph(DentalToolState)
graph.add_node('validate', validate_specifications)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
