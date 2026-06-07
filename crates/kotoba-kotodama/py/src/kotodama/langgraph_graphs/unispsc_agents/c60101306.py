from typing import TypedDict
from langgraph.graph import StateGraph, END

class StickerState(TypedDict):
    scent_profile: str
    material_safety_test: bool
    passed_compliance: bool

def validate_materials(state: StickerState):
    # Simulate safety protocol check
    is_safe = state.get('material_safety_test', False)
    return {'passed_compliance': is_safe}

def finalize_procurement(state: StickerState):
    return {'passed_compliance': True}

graph = StateGraph(StickerState)
graph.add_node('validate', validate_materials)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
