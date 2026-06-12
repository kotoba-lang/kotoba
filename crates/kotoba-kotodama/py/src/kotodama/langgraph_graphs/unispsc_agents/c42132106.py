from typing import TypedDict
from langgraph.graph import StateGraph, END

class BedspreadState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_medical_standards(state: BedspreadState):
    specs = state.get('spec_data', {})
    # Check for mandatory hospital grade compliance
    is_valid = 'antimicrobial' in specs and 'flame_retardant' in specs
    return {'validation_result': is_valid}

graph = StateGraph(BedspreadState)
graph.add_node('validate', validate_medical_standards)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
