from typing import TypedDict
from langgraph.graph import StateGraph, END

class ArcheryState(TypedDict):
    stand_id: str
    stability_score: float
    status: str

def validate_stability(state: ArcheryState):
    if state.get('stability_score', 0) > 8.0:
        return {'status': 'APPROVED'}
    return {'status': 'REJECTED'}

graph = StateGraph(ArcheryState)
graph.add_node('validate', validate_stability)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
