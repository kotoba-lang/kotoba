from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LabEquipmentState(TypedDict):
    specifications: dict
    validation_errors: List[str]
    approved: bool

def validate_specs(state: LabEquipmentState):
    specs = state.get('specifications', {})
    errors = []
    if specs.get('rpm', 0) <= 0:
        errors.append('Invalid RPM range')
    return {'validation_errors': errors, 'approved': len(errors) == 0}

graph = StateGraph(LabEquipmentState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
