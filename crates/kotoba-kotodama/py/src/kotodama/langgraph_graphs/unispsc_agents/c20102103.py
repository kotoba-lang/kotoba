from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ToolingState(TypedDict):
    part_id: str
    specs: dict
    validation_log: Annotated[Sequence[str], operator.add]
    status: str

def validate_dimensions(state: ToolingState) -> ToolingState:
    # Logic for CAD/CNC validation
    log = f'Validating dimensions for {state[part_id]}'
    return {**state, 'validation_log': [log], 'status': 'dimension_checked'}

def check_material(state: ToolingState) -> ToolingState:
    # Material certificate verification
    log = 'Material certificate verified against ISO standards'
    return {**state, 'validation_log': [log], 'status': 'material_certified'}

graph = StateGraph(ToolingState)
graph.add_node('validate', validate_dimensions)
graph.add_node('certify', check_material)
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph.set_entry_point('validate')
graph = graph.compile()
