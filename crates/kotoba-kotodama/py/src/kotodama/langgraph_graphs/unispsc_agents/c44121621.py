from typing import TypedDict
from langgraph.graph import StateGraph, END

class DeskPadState(TypedDict):
    material: str
    dimensions: dict
    is_compliant: bool

def validate_specs(state: DeskPadState):
    # Business logic for desktop accessory standardization
    state['is_compliant'] = state.get('material') in ['PU_leather', 'PVC', 'Recycled_Rubber']
    return state

workflow = StateGraph(DeskPadState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
