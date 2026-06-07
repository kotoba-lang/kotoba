from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BiologyGuideState(TypedDict):
    title: str
    is_peer_reviewed: bool
    validation_errors: List[str]

def validate_guide_specs(state: BiologyGuideState):
    errors = []
    if not state.get('is_peer_reviewed', False):
        errors.append('Reference material requires peer-reviewed status for procurement')
    return {'validation_errors': errors}

graph = StateGraph(BiologyGuideState)
graph.add_node('validate_guide', validate_guide_specs)
graph.set_entry_point('validate_guide')
graph.add_edge('validate_guide', END)
graph = graph.compile()
