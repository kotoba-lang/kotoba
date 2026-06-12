from typing import TypedDict
from langgraph.graph import StateGraph, END

class XRayTubeState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_specs(state: XRayTubeState):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('heat_capacity', 0) < 50000:
        results.append('Insufficient heat capacity')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def generate_compliance_report(state: XRayTubeState):
    return {'validation_results': state['validation_results'] + ['Report Generated']}

graph = StateGraph(XRayTubeState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_compliance_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
