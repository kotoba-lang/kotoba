from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AgHeliState(TypedDict):
    serial_number: str
    airworthiness_cert_valid: bool
    spray_system_test_passed: bool

def validate_airworthiness(state: AgHeliState):
    state['airworthiness_cert_valid'] = True
    return state

def validate_spray_system(state: AgHeliState):
    state['spray_system_test_passed'] = True
    return state

workflow = StateGraph(AgHeliState)
workflow.add_node('certify', validate_airworthiness)
workflow.add_node('spray_check', validate_spray_system)
workflow.add_edge('certify', 'spray_check')
workflow.add_edge('spray_check', END)
workflow.set_entry_point('certify')
graph = workflow.compile()
