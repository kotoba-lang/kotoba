from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EquipmentState(TypedDict):
    equipment_id: str
    specs: dict
    approved: bool

def validate_specs(state: EquipmentState):
    # Simulate CAD/Quality validation logic for Windsurfing gear
    specs = state.get('specs', {})
    is_valid = all(k in specs for k in ['material', 'dimensions'])
    print(f'Validating equipment {state.get('equipment_id')}: {is_valid}')
    return {'approved': is_valid}

workflow = StateGraph(EquipmentState)
workflow.add_node('validation', validate_specs)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
