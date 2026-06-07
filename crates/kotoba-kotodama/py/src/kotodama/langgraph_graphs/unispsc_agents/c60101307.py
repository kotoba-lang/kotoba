from langgraph.graph import StateGraph, END
from typing import TypedDict

class StickerProcessState(TypedDict):
    sticker_type: str
    material_certified: bool
    adhesive_strength: float

def validate_materials(state: StickerProcessState):
    state['material_certified'] = True
    return state

def check_quality(state: StickerProcessState):
    state['adhesive_strength'] = 0.95
    return state

graph = StateGraph(StickerProcessState)
graph.add_node('validate', validate_materials)
graph.add_node('quality', check_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', 'quality')
graph.add_edge('quality', END)
graph = graph.compile()
