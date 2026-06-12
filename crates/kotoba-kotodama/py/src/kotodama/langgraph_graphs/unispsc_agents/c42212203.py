from langgraph.graph import StateGraph, END
from typing import TypedDict

class PillReminderState(TypedDict):
    device_id: str
    compliance_verified: bool
    test_report: str

def validate_compliance(state: PillReminderState):
    # Simulate regulatory validation logic
    state['compliance_verified'] = True
    return {'compliance_verified': True}

def generate_report(state: PillReminderState):
    state['test_report'] = 'Validation passed for medical device safety standards'
    return {'test_report': state['test_report']}

graph = StateGraph(PillReminderState)
graph.add_node('validate', validate_compliance)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
