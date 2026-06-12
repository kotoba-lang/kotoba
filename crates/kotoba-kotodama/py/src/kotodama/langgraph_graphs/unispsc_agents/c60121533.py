from typing import TypedDict
from langgraph.graph import StateGraph, END

class EraserState(TypedDict):
    material: str
    size: str
    inspection_passed: bool

def validate_material(state: EraserState):
    state['inspection_passed'] = state.get('material') == 'vinyl'
    return state

workflow = StateGraph(EraserState)
workflow.add_node('validate', validate_material)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
