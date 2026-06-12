from typing import TypedDict
from langgraph.graph import StateGraph, END

class ReadingMaterialState(TypedDict):
    content_metadata: dict
    suitability_score: float
    approved: bool

def validate_curriculum(state: ReadingMaterialState):
    # Simulate alignment check
    state['approved'] = state.get('content_metadata', {}).get('level') == 'K-12'
    return state

def check_accessibility(state: ReadingMaterialState):
    # Simulate digital accessibility standards check
    if state.get('content_metadata', {}).get('digital'):
        state['suitability_score'] += 10.0
    return state

graph = StateGraph(ReadingMaterialState)
graph.add_node('curriculum_check', validate_curriculum)
graph.add_node('accessibility_check', check_accessibility)
graph.set_entry_point('curriculum_check')
graph.add_edge('curriculum_check', 'accessibility_check')
graph.add_edge('accessibility_check', END)
graph = graph.compile()
