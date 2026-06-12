from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LightingState(TypedDict):
    device_id: str
    protocol: str
    is_compatible: bool
    validation_log: List[str]

def validate_protocol(state: LightingState):
    protocol = state.get('protocol', '')
    is_valid = 'DMX' in protocol or 'RDM' in protocol
    return {'validation_log': [f'Protocol {protocol} check: {is_valid}'], 'is_compatible': is_valid}

def finalize_process(state: LightingState):
    return {'validation_log': state['validation_log'] + ['Device validation complete']}

graph = StateGraph(LightingState)
graph.add_node('validate', validate_protocol)
graph.add_node('finalize', finalize_process)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)

graph = graph.compile()
