from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    material: str
    food_grade_cert: bool
    passed_qa: bool

def validate_material(state: KitchenwareState):
    valid_materials = ['stainless steel', 'glass', 'bpa-free plastic']
    return {'passed_qa': state.get('material') in valid_materials and state.get('food_grade_cert')}

def route_by_qa(state: KitchenwareState):
    return 'process' if state.get('passed_qa') else END

graph = StateGraph(KitchenwareState)
graph.add_node('process', validate_material)
graph.set_entry_point('process')
graph.add_edge('process', END)
graph = graph.compile()
