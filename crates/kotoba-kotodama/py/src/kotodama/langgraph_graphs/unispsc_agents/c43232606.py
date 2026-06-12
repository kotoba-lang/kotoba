from typing import TypedDict
from langgraph.graph import StateGraph, END

class ComplianceState(TypedDict):
    requirements: list
    validation_status: bool
    report_generated: bool

def validate_compliance(state: ComplianceState):
    state['validation_status'] = True
    return {'validation_status': True}

def generate_audit_log(state: ComplianceState):
    state['report_generated'] = True
    return {'report_generated': True}

graph = StateGraph(ComplianceState)
graph.add_node('validate', validate_compliance)
graph.add_node('log', generate_audit_log)
graph.set_entry_point('validate')
graph.add_edge('validate', 'log')
graph.add_edge('log', END)
graph = graph.compile()
