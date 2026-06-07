from typing import TypedDict
from langgraph.graph import StateGraph, END

class GarmentBrushState(TypedDict):
    product_id: str
    material_check: bool
    approved: bool

def validate_material(state: GarmentBrushState):
    # Simulate material validation logic
    return {'material_check': True}

def approval_step(state: GarmentBrushState):
    # Final procurement check
    return {'approved': state['material_check']}

graph = StateGraph(GarmentBrushState)
graph.add_node('validate_material', validate_material)
graph.add_node('approval_step', approval_step)
graph.add_edge('validate_material', 'approval_step')
graph.add_edge('approval_step', END)
graph.set_entry_point('validate_material')

graph = graph.compile()
