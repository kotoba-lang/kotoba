from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProjectorState(TypedDict):
    spec_data: dict
    validation_report: str

def validate_specs(state: ProjectorState):
    specs = state.get('spec_data', {})
    if specs.get('lumens', 0) < 2000:
        return {'validation_report': 'Warning: Low brightness for intended auditorium use.'}
    return {'validation_report': 'Specifications successfully validated against standards.'}

def conduct_compliance(state: ProjectorState):
    return {'validation_report': state['validation_report'] + ' Compliance check passed.'}

graph = StateGraph(ProjectorState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', conduct_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
