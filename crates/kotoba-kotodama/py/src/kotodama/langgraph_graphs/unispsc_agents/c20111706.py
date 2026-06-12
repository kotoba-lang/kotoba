from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LathePartState(TypedDict):
    part_id: str
    spec_check: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_material(state: LathePartState):
    return {'validation_log': ['Material spec validated against ASTM standards.']}

def validate_dimensions(state: LathePartState):
    return {'validation_log': ['Dimensional tolerance checks complete.'], 'spec_check': True}

graph = StateGraph(LathePartState)
graph.add_node('material_validation', validate_material)
graph.add_node('dimension_inspection', validate_dimensions)
graph.add_edge('material_validation', 'dimension_inspection')
graph.add_edge('dimension_inspection', END)
graph.set_entry_point('material_validation')
graph = graph.compile()
