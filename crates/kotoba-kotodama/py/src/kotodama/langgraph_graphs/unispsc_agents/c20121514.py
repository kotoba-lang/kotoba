from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class FastenerState(TypedDict):
    part_number: str
    material_specs: dict
    torque_data: float
    validation_passed: bool
    error_log: List[str]

def validate_material(state: FastenerState):
    # Simulate material compliance check
    material = state.get('material_specs', {})
    valid = material.get('grade') in ['Grade 8', 'ASTM A574']
    return {'validation_passed': valid}

def process_torque(state: FastenerState):
    # Simulate torque validation
    torque = state.get('torque_data', 0.0)
    return {'validation_passed': state['validation_passed'] and (torque > 0)}

graph = StateGraph(FastenerState)
graph.add_node('validate_material', validate_material)
graph.add_node('process_torque', process_torque)
graph.add_edge('validate_material', 'process_torque')
graph.add_edge('process_torque', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
