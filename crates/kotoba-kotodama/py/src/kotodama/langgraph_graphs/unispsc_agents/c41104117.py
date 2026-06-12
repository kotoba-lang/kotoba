from typing import TypedDict
from langgraph.graph import StateGraph, END

class SpecimenState(TypedDict):
    spec_data: dict
    valid: bool

def validate_spec(state: SpecimenState):
    spec = state.get('spec_data', {})
    is_valid = all(key in spec for key in ['material', 'dimensions', 'sterilization'])
    return {'valid': is_valid}

def process_procurement(state: SpecimenState):
    print('Initiating procurement workflow for specimen holders')
    return state

graph = StateGraph(SpecimenState)
graph.add_node('validate', validate_spec)
graph.add_node('procure', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph = graph.compile()
