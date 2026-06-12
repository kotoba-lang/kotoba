from typing import TypedDict
from langgraph.graph import StateGraph, END

class StickerState(TypedDict):
    material: str
    adhesive: str
    is_compliant: bool

def validate_sticker(state: StickerState):
    # Business logic for sticker procurement compliance check
    valid = state.get('material') in ['paper', 'vinyl']
    return {'is_compliant': valid}

graph = StateGraph(StickerState)
graph.add_node('validate', validate_sticker)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
