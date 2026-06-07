from typing import TypedDict
from langgraph.graph import StateGraph, END

class EquipmentState(TypedDict):
    spec_sheet: dict
    validation_score: float
    status: str

def validate_specs(state: EquipmentState):
    specs = state.get('spec_sheet', {})
    # Logic for safety verification
    is_safe = specs.get('safety_certification_ce_ul', False)
    return {'validation_score': 1.0 if is_safe else 0.0, 'status': 'validated' if is_safe else 'failed'}

graph = StateGraph(EquipmentState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
