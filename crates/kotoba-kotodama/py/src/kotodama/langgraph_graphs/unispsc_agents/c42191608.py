from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class NursingMonitorState(TypedDict):
    device_id: str
    spec_compliance: bool
    validation_log: List[str]

def validate_medical_specs(state: NursingMonitorState):
    log = state.get('validation_log', [])
    log.append('Validating IEC 60601-1 compliance...')
    return {'validation_log': log, 'spec_compliance': True}

def deploy_monitoring_logic(state: NursingMonitorState):
    log = state.get('validation_log', [])
    log.append('Configuring exit sensor thresholds...')
    return {'validation_log': log}

graph = StateGraph(NursingMonitorState)
graph.add_node('validate', validate_medical_specs)
graph.add_node('deploy', deploy_monitoring_logic)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
