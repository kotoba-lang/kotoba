from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class FeedAdditiveState(TypedDict):
    additive_data: dict
    analysis_results: list[str]

def validate_composition(state: FeedAdditiveState):
    data = state.get('additive_data', {})
    purity = data.get('purity_percentage', 0)
    if purity < 95:
        return {'analysis_results': ['COMPOSITION_FAILURE: Purity below standard']}
    return {'analysis_results': ['COMPOSITION_PASS']}

def check_shelf_life(state: FeedAdditiveState):
    data = state.get('additive_data', {})
    shelf = data.get('shelf_life_days', 0)
    if shelf < 30:
        return {'analysis_results': ['STORAGE_WARNING: Short shelf life']}
    return {'analysis_results': ['STORAGE_OK']}

graph = StateGraph(FeedAdditiveState)
graph.add_node('validate_comp', validate_composition)
graph.add_node('check_shelf', check_shelf_life)
graph.set_entry_point('validate_comp')
graph.add_edge('validate_comp', 'check_shelf')
graph.add_edge('check_shelf', END)
graph = graph.compile()
