from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AerospaceState(TypedDict):
    part_id: str
    material_compliance: bool
    inspection_passed: bool
    history: List[str]

def validate_material(state: AerospaceState) -> AerospaceState:
    print(f'Validating material specs for {state[part_id]}')
    state['material_compliance'] = True
    state['history'].append('Material Validated')
    return state

def perform_inspection(state: AerospaceState) -> AerospaceState:
    print(f'Performing ultrasonic inspection on {state[part_id]}')
    state['inspection_passed'] = True
    state['history'].append('Inspection Passed')
    return state

builder = StateGraph(AerospaceState)
builder.add_node('validate', validate_material)
builder.add_node('inspect', perform_inspection)
builder.set_entry_point('validate')
builder.add_edge('validate', 'inspect')
builder.add_edge('inspect', END)
graph = builder.compile()
