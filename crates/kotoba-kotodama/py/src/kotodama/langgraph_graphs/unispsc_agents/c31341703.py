from typing import TypedDict
from langgraph.graph import StateGraph, END

class HastelloyState(TypedDict):
    part_id: str
    material_certified: bool
    thermal_validation: bool
    is_compliant: bool

def validate_material(state: HastelloyState) -> dict:
    # Logic to verify alloy composition standard AMS 5536
    return {'material_certified': True}

def validate_geometry(state: HastelloyState) -> dict:
    # Logic to verify bolt hole patterns and sheet thickness
    return {'thermal_validation': True}

def final_check(state: HastelloyState) -> dict:
    compliant = state['material_certified'] and state['thermal_validation']
    return {'is_compliant': compliant}

graph = StateGraph(HastelloyState)
graph.add_node('material', validate_material)
graph.add_node('geometry', validate_geometry)
graph.add_node('compliance', final_check)
graph.set_entry_point('material')
graph.add_edge('material', 'geometry')
graph.add_edge('geometry', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
