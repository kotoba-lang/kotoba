from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class PipeState(TypedDict):
    assembly_id: str
    inspection_results: Annotated[list, operator.add]
    is_approved: bool

def validate_geometry(state: PipeState):
    print('Validating copper pipe geometry and tolerances...')
    return {'inspection_results': ['Geometry Check Passed']}

def perform_nondestructive_test(state: PipeState):
    print('Performing ultrasonic weld inspection...')
    return {'inspection_results': ['NDT Passed'], 'is_approved': True}

graph = StateGraph(PipeState)
graph.add_node('geometry_check', validate_geometry)
graph.add_node('ndt_inspect', perform_nondestructive_test)
graph.add_edge('geometry_check', 'ndt_inspect')
graph.add_edge('ndt_inspect', END)
graph.set_entry_point('geometry_check')
graph = graph.compile()
