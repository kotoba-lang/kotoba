from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    part_number: str
    material_compliance: bool
    dimensional_check: bool
    approved: bool

def validate_material(state: State):
    return {'material_compliance': True}

def validate_dimensions(state: State):
    return {'dimensional_check': True}

def final_approval(state: State):
    return {'approved': state['material_compliance'] and state['dimensional_check']}

graph = StateGraph(State)
graph.add_node('material', validate_material)
graph.add_node('dimensions', validate_dimensions)
graph.add_node('approve', final_approval)
graph.set_entry_point('material')
graph.add_edge('material', 'dimensions')
graph.add_edge('dimensions', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
