from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class ResectoscopeState(TypedDict):
    serial_number: str
    is_sterile: bool
    calibration_status: bool
    log: Annotated[list, operator.add]

def validate_certification(state: ResectoscopeState):
    print('Validating medical device ISO compliance...')
    return {'log': ['Certification check passed']}

def inspect_optical_unit(state: ResectoscopeState):
    print('Running optical resolution test...')
    return {'log': ['Optical inspection complete']}

def finalize_clearance(state: ResectoscopeState):
    return {'log': ['Final procurement approval granted']}

graph = StateGraph(ResectoscopeState)
graph.add_node('certify', validate_certification)
graph.add_node('inspect', inspect_optical_unit)
graph.add_node('approve', finalize_clearance)
graph.set_entry_point('certify')
graph.add_edge('certify', 'inspect')
graph.add_edge('inspect', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
