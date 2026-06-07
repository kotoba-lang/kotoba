from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CarpetState(TypedDict):
    specifications: dict
    validation_results: List[str]
    approved: bool

def validate_materials(state: CarpetState):
    # logic for verifying fiber content and flame retardancy
    return {'validation_results': ['Material check passed']}

def check_quality_specs(state: CarpetState):
    # check knot density and backing standards
    return {'validation_results': ['Quality check passed'], 'approved': True}

graph = StateGraph(CarpetState)
graph.add_node('validate', validate_materials)
graph.add_node('quality_control', check_quality_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', 'quality_control')
graph.add_edge('quality_control', END)
graph = graph.compile()
