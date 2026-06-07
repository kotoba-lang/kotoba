from typing import TypedDict
from langgraph.graph import StateGraph, END

class PlanningSystemState(TypedDict):
    requirements: dict
    validation_passed: bool
    deployment_ready: bool

def validate_requirements(state: PlanningSystemState):
    state['validation_passed'] = bool(state.get('requirements', {}).get('scope'))
    return state

def check_compliance(state: PlanningSystemState):
    state['deployment_ready'] = state.get('validation_passed', False)
    return state

graph = StateGraph(PlanningSystemState)
graph.add_node('validate', validate_requirements)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
