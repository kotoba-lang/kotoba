from typing import TypedDict
from langgraph.graph import StateGraph, END

class GearState(TypedDict):
    gear_specs: dict
    validation_results: dict

def validate_specs(state: GearState):
    specs = state.get('gear_specs', {})
    # Logic to validate manufacturing tolerances for bevel gears
    is_valid = all(k in specs for k in ['module', 'pressure_angle', 'material_grade'])
    return {'validation_results': {'passed': is_valid, 'risk_alert': False}}

def route_by_material(state: GearState):
    material = state['gear_specs'].get('material_grade')
    if material == 'Titanium':
        return 'export_review'
    return 'end'

graph = StateGraph(GearState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
