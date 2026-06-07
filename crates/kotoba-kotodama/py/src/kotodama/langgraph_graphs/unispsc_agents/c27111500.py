from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToolSpecState(TypedDict):
    tool_type: str
    material_spec: str
    is_compliant: bool
    validation_log: List[str]

def validate_tool_specs(state: ToolSpecState):
    log = state.get('validation_log', [])
    valid = True
    if not state.get('material_spec'):
        log.append('Missing material specification.')
        valid = False
    return {'is_compliant': valid, 'validation_log': log}

def finalize_order(state: ToolSpecState):
    return {'validation_log': state['validation_log'] + ['Order ready for procurement.']}

graph = StateGraph(ToolSpecState)
graph.add_node('validate', validate_tool_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
