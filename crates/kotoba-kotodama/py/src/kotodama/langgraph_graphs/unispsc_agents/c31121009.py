from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BerylliumProcessState(TypedDict):
    part_id: str
    safety_check_passed: bool
    compliance_cleared: bool

def validate_materials(state: BerylliumProcessState):
    # Simulate stringent toxicity and purity validation
    state['safety_check_passed'] = True
    return state

def check_export_compliance(state: BerylliumProcessState):
    # Simulate dual-use export control checks
    state['compliance_cleared'] = True
    return state

graph = StateGraph(BerylliumProcessState)
graph.add_node('safety_check', validate_materials)
graph.add_node('compliance_check', check_export_compliance)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
