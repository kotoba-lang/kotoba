from typing import TypedDict
from langgraph.graph import StateGraph, END

class LocomotiveState(TypedDict):
    spec_data: dict
    validation_report: dict

def validate_specs(state: LocomotiveState):
    specs = state.get('spec_data', {})
    report = {'is_valid': True, 'errors': []}
    if not specs.get('emission_standard'):
        report['is_valid'] = False
        report['errors'].append('Missing emission standard.')
    return {'validation_report': report}

def route_by_compliance(state: LocomotiveState):
    if state['validation_report']['is_valid']:
        return 'final'
    return 'alert'

graph = StateGraph(LocomotiveState)
graph.add_node('validator', validate_specs)
graph.add_node('final', lambda s: s)
graph.add_node('alert', lambda s: s)
graph.set_entry_point('validator')
graph.add_conditional_edges('validator', route_by_compliance)
graph.add_edge('final', END)
graph.add_edge('alert', END)
graph = graph.compile()
