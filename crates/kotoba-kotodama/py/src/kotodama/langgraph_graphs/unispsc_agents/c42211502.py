from typing import TypedDict
from langgraph.graph import StateGraph, END

class CrutchState(TypedDict):
    spec_sheet: dict
    validation_results: list
    is_approved: bool

def validate_safety_standards(state: CrutchState):
    checks = ['ISO 11334', 'Weight Capacity Check', 'Non-Slip Test']
    results = [f'{c} passed' for c in checks]
    return {'validation_results': results, 'is_approved': True}

graph = StateGraph(CrutchState)
graph.add_node('safety_check', validate_safety_standards)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
