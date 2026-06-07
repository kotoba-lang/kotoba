from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AircraftComponentState(TypedDict):
    part_number: str
    specifications: dict
    compliance_checked: bool
    approved: bool

def validate_specs(state: AircraftComponentState):
    specs = state.get('specifications', {})
    required = ['AS9100', 'airflow', 'voltage']
    state['compliance_checked'] = all(k in specs for k in required)
    return state

def workflow_decision(state: AircraftComponentState):
    return 'approved' if state['compliance_checked'] else 'rejected'

graph = StateGraph(AircraftComponentState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', workflow_decision, {'approved': END, 'rejected': END})
graph = graph.compile()
