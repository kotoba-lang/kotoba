from langgraph.graph import StateGraph, END
from typing import TypedDict
class ShuttlecockState(TypedDict):
    quantity: int
    spec_check: bool
    quality_score: float
def validate_materials(state: ShuttlecockState):
    return {'spec_check': True}
def quality_inspection(state: ShuttlecockState):
    return {'quality_score': 0.95}
graph = StateGraph(ShuttlecockState)
graph.add_node('validate', validate_materials)
graph.add_node('inspect', quality_inspection)
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph.set_entry_point('validate')
graph = graph.compile()
