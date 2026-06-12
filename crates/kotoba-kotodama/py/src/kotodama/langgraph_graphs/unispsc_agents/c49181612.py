from typing import TypedDict
from langgraph.graph import StateGraph, END

class ArcheryBackstopState(TypedDict):
    spec_dimensions: str
    material_certified: bool
    safety_rating: int

def validate_specs(state: ArcheryBackstopState):
    if state.get('safety_rating', 0) < 50:
        return {'material_certified': False}
    return {'material_certified': True}

workflow = StateGraph(ArcheryBackstopState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
