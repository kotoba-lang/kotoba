from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CarpetState(TypedDict):
    area_sqm: float
    material_type: str
    fire_safety_certified: bool
    validation_log: List[str]

def validate_carpet(state: CarpetState) -> CarpetState:
    logs = []
    if state.get('area_sqm', 0) <= 0:
        logs.append('Invalid area')
    if not state.get('fire_safety_certified', False):
        logs.append('Missing fire safety certification')
    return {'validation_log': logs}

def process_deployment(state: CarpetState) -> CarpetState:
    return {'validation_log': state['validation_log'] + ['Deployment specs processed']}

graph = StateGraph(CarpetState)
graph.add_node('validate', validate_carpet)
graph.add_node('process', process_deployment)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
