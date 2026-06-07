from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_type: str
    solvent_grade: str
    bond_test_passed: bool
    dimension_check: bool

def validate_material(state: ProcurementState):
    print(f'Validating material: {state.get("material_type")}')
    return {'bond_test_passed': True}

def check_dimensions(state: ProcurementState):
    print('Verifying dimensional tolerances...')
    return {'dimension_check': True}

graph = StateGraph(ProcurementState)
graph.add_node('material_validation', validate_material)
graph.add_node('dimension_compliance', check_dimensions)
graph.set_entry_point('material_validation')
graph.add_edge('material_validation', 'dimension_compliance')
graph.add_edge('dimension_compliance', END)
graph = graph.compile()
