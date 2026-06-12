from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    part_number: str
    material_spec: str
    tolerance_checked: bool
    ndt_passed: bool

def validate_materials(state: ForgingState) -> ForgingState:
    print(f'Validating material specifications for {state.get('part_number')}')
    return {**state, 'material_spec': 'Verified'}

def perform_ndt_inspection(state: ForgingState) -> ForgingState:
    print('Running ultrasonic NDT inspection...')
    return {**state, 'ndt_passed': True}

graph_builder = StateGraph(ForgingState)
graph_builder.add_node('verify_material', validate_materials)
graph_builder.add_node('ndt_scan', perform_ndt_inspection)
graph_builder.set_entry_point('verify_material')
graph_builder.add_edge('verify_material', 'ndt_scan')
graph_builder.add_edge('ndt_scan', END)
graph = graph_builder.compile()
