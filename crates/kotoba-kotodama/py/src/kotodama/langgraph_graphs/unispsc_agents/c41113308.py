from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AnalyzerState(TypedDict):
    device_id: str
    calibration_status: bool
    validation_errors: List[str]

def validate_specs(state: AnalyzerState):
    errors = []
    if not state.get('calibration_status'):
        errors.append('Device must be calibrated before deployment.')
    return {'validation_errors': errors}

def deploy_analyzer(state: AnalyzerState):
    if not state['validation_errors']:
        print(f'Deploying analyzer {state['device_id']}')
    return {'validation_errors': state['validation_errors']}

graph = StateGraph(AnalyzerState)
graph.add_node('validate', validate_specs)
graph.add_node('deploy', deploy_analyzer)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
