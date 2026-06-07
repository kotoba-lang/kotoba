from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_mechanical_specs(state: RobotState):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('repeatability', 0) > 0.05:
        results.append('Precision error: tolerance exceeds 0.05mm')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_mechanical_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
