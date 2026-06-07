from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PlumbingState(TypedDict):
    vent_specs: dict
    validation_log: List[str]
    approved: bool

def validate_specs(state: PlumbingState):
    validator = state.get('vent_specs', {})
    log = []
    if 'diameter' not in validator:
        log.append('Missing diameter specification')
    return {'validation_log': log, 'approved': len(log) == 0}

graph = StateGraph(PlumbingState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
