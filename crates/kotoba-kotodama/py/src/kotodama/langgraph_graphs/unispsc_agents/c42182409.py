from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AnalysisState(TypedDict):
    device_id: str
    calibration_data: dict
    compliance_report: str
    approved: bool

def validate_compliance(state: AnalysisState):
    # Simulate validation logic for medical device standards
    state['approved'] = state.get('calibration_data', {}).get('is_valid', False)
    return state

def generate_report(state: AnalysisState):
    state['compliance_report'] = 'Compliance Verified' if state['approved'] else 'Compliance Failed'
    return state

graph = StateGraph(AnalysisState)
graph.add_node('validate', validate_compliance)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
