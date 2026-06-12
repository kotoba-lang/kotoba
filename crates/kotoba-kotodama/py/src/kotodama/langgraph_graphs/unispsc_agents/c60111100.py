from typing import TypedDict
from langgraph.graph import StateGraph, END

class BulletinBoardState(TypedDict):
    material: str
    dimensions: str
    is_fire_rated: bool

def validate_specs(state: BulletinBoardState):
    if not state.get('dimensions'):
        raise ValueError('Dimenions required')
    return 'validated'

graph = StateGraph(BulletinBoardState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
