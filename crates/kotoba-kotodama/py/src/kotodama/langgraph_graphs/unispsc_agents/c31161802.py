from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WasherState(TypedDict):
    material: str
    taper_angle: float
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: WasherState):
    log = []
    compliant = True
    if not state.get('material'):
        log.append('Material missing')
        compliant = False
    if not (0 < state.get('taper_angle', 0) < 90):
        log.append('Invalid taper angle')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

graph = StateGraph(WasherState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
