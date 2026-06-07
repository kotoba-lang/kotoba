from typing import TypedDict
from langgraph.graph import StateGraph, END

class PogState(TypedDict):
    material: str
    compliance_checked: bool
    approved: bool

def validate_materials(state: PogState):
    allowed = ['cardboard', 'plastic', 'paper']
    return {'compliance_checked': state.get('material') in allowed}

def final_approval(state: PogState):
    return {'approved': state.get('compliance_checked') is True}

graph = StateGraph(PogState)
graph.add_node('validation', validate_materials)
graph.add_node('approval', final_approval)
graph.add_edge('validation', 'approval')
graph.add_edge('approval', END)
graph.set_entry_point('validation')
graph = graph.compile()
