from typing import TypedDict
from langgraph.graph import StateGraph, END

class StickerState(TypedDict):
    material: str
    adhesion_rating: float
    visual_quality_score: float

def validate_materials(state: StickerState):
    print('Validating non-toxic materials...')
    return {'material': 'Certified-Non-Toxic'}

def check_adhesion(state: StickerState):
    print('Checking adhesive consistency...')
    return {'adhesion_rating': 9.5}

graph = StateGraph(StickerState)
graph.add_node('material_check', validate_materials)
graph.add_node('adhesion_check', check_adhesion)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'adhesion_check')
graph.add_edge('adhesion_check', END)
graph = graph.compile()
