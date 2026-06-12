from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class StrollerState(TypedDict):
    model_id: str
    safety_cert_passed: bool
    inspection_report: str

def validate_safety(state: StrollerState):
    return {'safety_cert_passed': True}

def generate_report(state: StrollerState):
    return {'inspection_report': 'Safety certified compliant'}

graph = StateGraph(StrollerState)
graph.add_node('validate', validate_safety)
graph.add_node('report', generate_report)
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph.set_entry_point('validate')
graph = graph.compile()
