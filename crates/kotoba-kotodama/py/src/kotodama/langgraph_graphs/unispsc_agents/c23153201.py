from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToolSpecState(TypedDict):
    spec_data: dict
    validation_log: List[str]
    is_compliant: bool

def validate_specs(state: ToolSpecState):
    log = state.get('validation_log', [])
    specs = state.get('spec_data', {})
    # Check for required safety certs
    if 'safety_cert' not in specs:
        log.append('Missing safety certification')
        return {'validation_log': log, 'is_compliant': False}
    return {'validation_log': ['Safety specs verified'], 'is_compliant': True}

graph = StateGraph(ToolSpecState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
