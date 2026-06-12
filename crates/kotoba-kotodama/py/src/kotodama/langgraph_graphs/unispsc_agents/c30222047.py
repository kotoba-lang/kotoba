from typing import TypedDict
from langgraph.graph import StateGraph, END

class AccessRoadState(TypedDict):
    project_specs: dict
    validation_report: list
    status: str

def validate_civil_specs(state: AccessRoadState):
    specs = state.get('project_specs', {})
    required = ['load_bearing', 'drainage']
    valid = all(key in specs for key in required)
    return {'validation_report': ['Passed'] if valid else ['Failed specs']}

def approval_workflow(state: AccessRoadState):
    return {'status': 'Approved'}

graph = StateGraph(AccessRoadState)
graph.add_node('validate', validate_civil_specs)
graph.add_node('approve', approval_workflow)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
