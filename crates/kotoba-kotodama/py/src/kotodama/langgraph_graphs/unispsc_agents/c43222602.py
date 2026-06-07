from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HeadendState(TypedDict):
    equipment_specs: dict
    validation_log: List[str]
    approved: bool

def validate_specs(state: HeadendState):
    specs = state.get('equipment_specs', {})
    log = []
    if 'encoding_standard' not in specs:
        log.append("Missing mandatory encoding standard")
    return {'validation_log': log, 'approved': len(log) == 0}

graph = StateGraph(HeadendState)
graph.add_node("validate", validate_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()
