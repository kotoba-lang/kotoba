from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class State(TypedDict):
    material_type: str
    validation_checklist: List[str]
    is_approved: bool

def validate_material(state: State):
    checks = ['content_authenticity', 'formatting_compliance']
    return {'validation_checklist': checks, 'is_approved': True}

graph = StateGraph(State)
graph.add_node('validate', validate_material)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
