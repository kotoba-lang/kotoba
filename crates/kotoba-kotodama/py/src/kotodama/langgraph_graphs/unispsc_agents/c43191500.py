from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PeripheralsState(TypedDict):
    device_id: str
    specs: dict
    validation_log: List[str]
    approved: bool

def validate_device_spec(state: PeripheralsState):
    log = state.get('validation_log', [])
    specs = state.get('specs', {})
    if 'mtbf' in specs and specs['mtbf'] >= 50000:
        log.append('MTBF meets enterprise standards')
        return {'validation_log': log, 'approved': True}
    log.append('MTBF below enterprise standards')
    return {'validation_log': log, 'approved': False}

def process_deployment(state: PeripheralsState):
    return {'validation_log': state['validation_log'] + ['Deployment route finalized']}

graph = StateGraph(PeripheralsState)
graph.add_node('validate', validate_device_spec)
graph.add_node('deploy', process_deployment)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
